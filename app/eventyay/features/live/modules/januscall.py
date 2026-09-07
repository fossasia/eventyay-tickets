import hashlib
import json
import secrets
import time

from channels.db import database_sync_to_async
from django.conf import settings
from redis.asyncio.lock import Lock
from sentry_sdk import capture_exception

from eventyay.base.models import JanusServer, User
from eventyay.base.services import turn
from eventyay.base.services.janus import (
    JanusError,
    JanusPluginError,
    choose_server,
    create_videoroom,
    videoroom_add_token_if_exists,
    videoroom_kick,
    videoroom_moderate,
)
from eventyay.base.services.roulette import is_member_of_roulette_call
from eventyay.base.services.user import get_public_user
from eventyay.core.permissions import Permission
from eventyay.core.utils.redis import aredis
from eventyay.features.live.channels import GROUP_ROOM, GROUP_USER
from eventyay.features.live.decorators import (
    command,
    event,
    require_event_permission,
    room_action,
)
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


class JanusCallModule(BaseModule):
    prefix = "januscall"
    WAITING_ROOM_TTL = 3600

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.media_state_rooms = {}
        self.raise_hand_rooms = {}
        self.waiting_admission_rooms = {}

    @database_sync_to_async
    def _servers(self):
        return choose_server(self.consumer.event), turn.choose_server(self.consumer.event)

    @staticmethod
    def _empty_media_state():
        return {
            "micOn": False,
            "cameraOn": False,
            "sharingScreen": False,
        }

    @staticmethod
    def _normalize_media_state(body):
        return {
            "micOn": bool(body.get("micOn")),
            "cameraOn": bool(body.get("cameraOn")),
            "sharingScreen": bool(body.get("sharingScreen")),
        }

    @staticmethod
    def _media_state_key(room_id):
        return f"januscall:media_state:{room_id}"

    @staticmethod
    def _media_state_socket_key(room_id, user_id):
        return f"januscall:media_state:{room_id}:sockets:{user_id}"

    @staticmethod
    def _room_feed_user_key(room_id, feed_id):
        return f"januscall:room:{room_id}:feed:{feed_id}"

    @staticmethod
    def _room_user_feeds_key(room_id, user_id):
        return f"januscall:room:{room_id}:user:{user_id}:feeds"

    @staticmethod
    def _room_feeds_key(room_id):
        return f"januscall:room:{room_id}:feeds"

    @staticmethod
    def _waiting_room_key(room_id):
        return f"januscall:waiting:{room_id}"

    @staticmethod
    def _spotlight_key(room_id):
        return f"januscall:spotlight:{room_id}"

    @staticmethod
    def _raise_hands_key(room_id):
        return f"januscall:raise_hands:{room_id}"

    @staticmethod
    def _is_waiting_room_enabled(module_config):
        return bool(
            module_config.get("waiting_room_enabled", False)
            or module_config.get("waiting_room", False)
        )

    @staticmethod
    def _decode_media_state(raw_state):
        try:
            state = json.loads(raw_state.decode())
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
            return JanusCallModule._empty_media_state()
        return JanusCallModule._normalize_media_state(state)

    @classmethod
    def _aggregate_media_states(cls, raw_socket_states):
        state = cls._empty_media_state()
        for raw_state in raw_socket_states:
            socket_state = cls._decode_media_state(raw_state)
            for key in state:
                state[key] = state[key] or socket_state[key]
        return state

    @classmethod
    def _decode_media_states(cls, raw_states):
        return {
            key.decode(): cls._decode_media_state(value)
            for key, value in raw_states.items()
        }

    async def _set_media_state(self, room_id, state):
        user_id = str(self.consumer.user.pk)
        redis_key = self._media_state_key(room_id)
        socket_key = self._media_state_socket_key(room_id, user_id)
        async with aredis(redis_key) as redis:
            await redis.hset(socket_key, self.consumer.socket_id, json.dumps(state))
            await redis.expire(socket_key, 3600 * 24)

            raw_socket_states = await redis.hvals(socket_key)
            aggregate_state = self._aggregate_media_states(raw_socket_states)
            await redis.hset(redis_key, user_id, json.dumps(aggregate_state))
            await redis.expire(redis_key, 3600 * 24)
            raw_states = await redis.hgetall(redis_key)

        return aggregate_state, self._decode_media_states(raw_states)

    async def _remove_media_state(self, room_id):
        if not self.consumer.user:
            return None

        user_id = str(self.consumer.user.pk)
        redis_key = self._media_state_key(room_id)
        socket_key = self._media_state_socket_key(room_id, user_id)
        async with aredis(redis_key) as redis:
            await redis.hdel(socket_key, self.consumer.socket_id)
            raw_socket_states = await redis.hvals(socket_key)
            if raw_socket_states:
                aggregate_state = self._aggregate_media_states(raw_socket_states)
                await redis.hset(redis_key, user_id, json.dumps(aggregate_state))
                await redis.expire(socket_key, 3600 * 24)
                await redis.expire(redis_key, 3600 * 24)
                return aggregate_state

            await redis.delete(socket_key)
            await redis.hdel(redis_key, user_id)
            return self._empty_media_state()

    async def cleanup_media_state_for_room(self, room):
        room_id = str(room.pk)
        if room_id not in self.media_state_rooms:
            return

        state = await self._remove_media_state(room_id)
        self.media_state_rooms.pop(room_id, None)
        if state is None:
            return

        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=room.pk),
            {
                "type": "januscall.media_state",
                "room": room_id,
                "user": str(self.consumer.user.pk),
                "state": state,
            },
        )

    async def cleanup_raise_hand_for_room(self, room):
        room_id = str(room.pk)
        if room_id not in self.raise_hand_rooms or not self.consumer.user:
            return

        state = await self._set_raise_hand(room.pk, self.consumer.user, False)
        self.raise_hand_rooms.pop(room_id, None)
        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=room.pk),
            {
                "type": "januscall.raise_hand",
                "room": room_id,
                "user": str(self.consumer.user.pk),
                "state": state,
            },
        )

    async def _subscribe_room_events(self):
        await self.consumer.channel_layer.group_add(
            GROUP_ROOM.format(id=self.room.pk),
            self.consumer.channel_name,
        )

    @command("room_url")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def room_url(self, body):
        await self._subscribe_room_events()
        if (
            self._is_waiting_room_enabled(self.module_config)
            and not await self._can_moderate_room()
        ):
            pending_user = await self._add_pending_admission()
            await self.consumer.send_success(
                {
                    "status": "pending",
                    "room": str(self.room.pk),
                    "user": pending_user,
                    "fallback": "Users remain in the waiting room until a host admits or denies them.",
                }
            )
            return

        room_data = await self._get_or_create_janus_room(
            f"room:{self.room.id}", audiobridge=True
        )
        is_mod = await self._can_moderate_room()
        room_data["isModerator"] = is_mod
        room_data["status"] = "ready"
        room_data["config"] = {
            "start_with_audio_muted": bool(
                self.module_config.get("start_with_audio_muted")
                or self.module_config.get("auto_mute")
            ),
            "start_with_video_muted": bool(
                self.module_config.get("start_with_video_muted")
            ),
            "disable_cam": bool(self.module_config.get("disable_cam")) and not is_mod,
            "disable_chat": bool(self.module_config.get("disable_chat")) and not is_mod,
        }
        await self.consumer.send_success(room_data)

    @command("waiting_room.list")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def waiting_room_list(self, body):
        if not await self._can_moderate_room():
            raise ConsumerException("protocol.denied", "Permission denied.")

        await self.consumer.send_success(
            {
                "room": str(self.room.pk),
                "users": await self._pending_admissions(),
            }
        )

    @command("waiting_room.cancel")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def waiting_room_cancel(self, body):
        await self._remove_pending_admission(self.consumer.user.pk, status="cancelled")
        self.waiting_admission_rooms.pop(str(self.room.pk), None)
        await self.consumer.send_success({"room": str(self.room.pk)})

    @command("waiting_room.admit")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def waiting_room_admit(self, body):
        if not await self._can_moderate_room():
            raise ConsumerException("protocol.denied", "Permission denied.")

        target_user = await self._get_waiting_user(body.get("user"))
        room_data = await self._get_or_create_janus_room(
            f"room:{self.room.id}",
            audiobridge=True,
            user=target_user,
        )
        room_data["isModerator"] = await self.consumer.event.has_permission_async(
            user=target_user,
            permission=[
                Permission.ROOM_JANUSCALL_MODERATE,
                Permission.ROOM_UPDATE,
                Permission.EVENT_UPDATE,
            ],
            room=self.room,
        )
        room_data["status"] = "ready"

        await self._remove_pending_admission(target_user.pk, status="admitted")
        await self.consumer.channel_layer.group_send(
            GROUP_USER.format(id=target_user.pk),
            {
                "type": "januscall.admission_result",
                "room": str(self.room.pk),
                "status": "admitted",
                "session": room_data,
            },
        )
        await self.consumer.send_success(
            {
                "room": str(self.room.pk),
                "user": str(target_user.pk),
            }
        )

    @command("waiting_room.deny")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def waiting_room_deny(self, body):
        if not await self._can_moderate_room():
            raise ConsumerException("protocol.denied", "Permission denied.")

        target_user = await self._get_waiting_user(body.get("user"))
        await self._remove_pending_admission(target_user.pk, status="denied")
        await self.consumer.channel_layer.group_send(
            GROUP_USER.format(id=target_user.pk),
            {
                "type": "januscall.admission_result",
                "room": str(self.room.pk),
                "status": "denied",
            },
        )
        await self.consumer.send_success(
            {
                "room": str(self.room.pk),
                "user": str(target_user.pk),
            }
        )

    @command("media_state")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def media_state(self, body):
        await self._subscribe_room_events()
        state = self._normalize_media_state(body)
        if self.module_config.get("disable_cam") and not await self._can_moderate_room():
            state["video"] = False
        user_id = str(self.consumer.user.pk)
        state, states = await self._set_media_state(self.room.pk, state)
        self.media_state_rooms[str(self.room.pk)] = self.room

        await self.consumer.send_success({"states": states})
        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            {
                "type": "januscall.media_state",
                "room": str(self.room.pk),
                "user": user_id,
                "state": state,
            },
        )

    @command("media_state.list")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def media_state_list(self, body):
        await self._subscribe_room_events()
        redis_key = self._media_state_key(self.room.pk)
        async with aredis(redis_key) as redis:
            raw_states = await redis.hgetall(redis_key)
        await self.consumer.send_success({"states": self._decode_media_states(raw_states)})

    @command("raise_hand")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def raise_hand(self, body):
        await self._subscribe_room_events()
        requested_state = body.get("raised")
        was_raised = await self._is_hand_raised(self.room.pk, self.consumer.user.pk)
        if requested_state is None:
            requested_state = not was_raised
        state = await self._set_raise_hand(
            self.room.pk, self.consumer.user, bool(requested_state)
        )
        if state["raised"]:
            self.raise_hand_rooms[str(self.room.pk)] = self.room
        else:
            self.raise_hand_rooms.pop(str(self.room.pk), None)

        payload = {
            "type": "januscall.raise_hand",
            "room": str(self.room.pk),
            "user": str(self.consumer.user.pk),
            "state": state,
        }
        await self.consumer.send_success({"room": str(self.room.pk), "state": state})
        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            payload,
        )
        if state["raised"] and not was_raised:
            await self.consumer.channel_layer.group_send(
                GROUP_ROOM.format(id=self.room.pk),
                {
                    "type": "januscall.raise_hand_notification",
                    "room": str(self.room.pk),
                    "user": str(self.consumer.user.pk),
                    "display_name": state.get("display_name") or "",
                    "raised_at": state.get("raised_at"),
                },
            )

    @command("lower_hand")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def lower_hand(self, body):
        await self._subscribe_room_events()
        target_user = await self._get_raise_hand_target(body.get("user"))
        if (
            target_user.pk != self.consumer.user.pk
            and not await self._can_moderate_room()
        ):
            raise ConsumerException("protocol.denied", "Permission denied.")

        state = await self._set_raise_hand(self.room.pk, target_user, False)
        payload = {
            "type": "januscall.raise_hand",
            "room": str(self.room.pk),
            "user": str(target_user.pk),
            "state": state,
            "moderator": str(self.consumer.user.pk),
        }
        await self.consumer.send_success(
            {"room": str(self.room.pk), "user": str(target_user.pk), "state": state}
        )
        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            payload,
        )

    @command("raise_hand.list")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def raise_hand_list(self, body):
        await self._subscribe_room_events()
        await self.consumer.send_success(
            {
                "room": str(self.room.pk),
                "hands": await self._raised_hands(self.room.pk),
            }
        )

    @command("mute_participant")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def mute_participant(self, body):
        await self._moderate_participant(
            body,
            action="mute_participant",
            janus_moderation={"mute_audio": True},
        )

    @command("stop_participant_video")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def stop_participant_video(self, body):
        await self._moderate_participant(
            body,
            action="stop_participant_video",
            janus_moderation={"mute_video": True},
        )

    @command("disable_screenshare")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def disable_screenshare(self, body):
        await self._moderate_participant(
            body,
            action="disable_screenshare",
            janus_moderation={"mute_video": True},
        )

    @command("remove_participant")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def remove_participant(self, body):
        await self._moderate_participant(body, action="remove_participant", kick=True)

    @command("end_meeting")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def end_meeting(self, body):
        await self._end_meeting_for_all()

    @command("spotlight")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def spotlight(self, body):
        await self._subscribe_room_events()
        if not await self._can_moderate_room():
            raise ConsumerException("protocol.denied", "Permission denied.")

        target_user = body.get("target_user")
        target_user = await self._validate_spotlight_user(target_user)
        async with aredis(self._spotlight_key(self.room.pk)) as redis:
            if target_user:
                await redis.setex(
                    self._spotlight_key(self.room.pk), 3600 * 24, target_user
                )
            else:
                await redis.delete(self._spotlight_key(self.room.pk))

        payload = {
            "type": "januscall.spotlight",
            "room": str(self.room.pk),
            "target_user": target_user,
            "moderator": str(self.consumer.user.pk),
        }
        await self.consumer.send_success(
            {
                "room": str(self.room.pk),
                "target_user": target_user,
            }
        )
        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            payload,
        )

    @command("spotlight.state")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def spotlight_state(self, body):
        await self._subscribe_room_events()
        async with aredis(self._spotlight_key(self.room.pk)) as redis:
            target_user = await redis.get(self._spotlight_key(self.room.pk))
        await self.consumer.send_success(
            {
                "room": str(self.room.pk),
                "target_user": target_user.decode() if target_user else None,
            }
        )

    async def _validate_spotlight_user(self, target_user):
        if not target_user:
            return None

        target_user = str(target_user)
        try:
            target_user_pk = int(target_user)
        except (TypeError, ValueError):
            raise ConsumerException("janus.target_not_found", "Participant not found.")

        try:
            await database_sync_to_async(User.objects.get)(
                event=self.consumer.event,
                pk=target_user_pk,
            )
        except User.DoesNotExist:
            raise ConsumerException("janus.target_not_found", "Participant not found.")

        async with aredis(self._room_user_feeds_key(self.room.pk, target_user)) as redis:
            feed_ids = await redis.smembers(
                self._room_user_feeds_key(self.room.pk, target_user)
            )
        if not feed_ids:
            raise ConsumerException("janus.target_not_found", "Participant not found.")

        return target_user

    @command("channel_url")
    async def channel_url(self, body):
        channel_id = body.get("channel")
        if not await self.consumer.user.is_member_of_channel_async(channel_id):
            raise ConsumerException("janus.denied")
        room_data = await self._get_or_create_janus_room(f"channel:{channel_id}")
        await self.consumer.send_success(room_data)

    @command("roulette_url")
    async def roulette_url(self, body):
        call_id = body.get("call_id")
        if not await is_member_of_roulette_call(call_id, self.consumer.user):
            raise ConsumerException("janus.denied")
        room_data = await self._get_or_create_janus_room(f"roulette:{call_id}")
        await self.consumer.send_success(room_data)

    async def _add_pending_admission(self):
        pending_user = {
            "id": str(self.consumer.user.pk),
            "display_name": self.consumer.user.profile.get("display_name") or "",
            "joined_at": int(time.time()),
        }
        async with aredis(self._waiting_room_key(self.room.pk)) as redis:
            await redis.hset(
                self._waiting_room_key(self.room.pk),
                pending_user["id"],
                json.dumps(pending_user),
            )
            await redis.expire(
                self._waiting_room_key(self.room.pk), self.WAITING_ROOM_TTL
            )

        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            {
                "type": "januscall.waiting_room_updated",
                "room": str(self.room.pk),
                "action": "pending",
                "user": pending_user,
            },
        )
        self.waiting_admission_rooms[str(self.room.pk)] = self.room
        return pending_user

    async def _pending_admissions(self):
        async with aredis(self._waiting_room_key(self.room.pk)) as redis:
            raw_users = await redis.hvals(self._waiting_room_key(self.room.pk))

        users = []
        for raw_user in raw_users:
            try:
                users.append(json.loads(raw_user.decode()))
            except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
                continue
        return sorted(users, key=lambda user: user.get("joined_at", 0))

    async def _is_hand_raised(self, room_id, user_id):
        async with aredis(self._raise_hands_key(room_id)) as redis:
            return bool(
                await redis.hexists(self._raise_hands_key(room_id), str(user_id))
            )

    async def _set_raise_hand(self, room_id, user, raised):
        user_id = str(user.pk)
        redis_key = self._raise_hands_key(room_id)
        async with aredis(redis_key) as redis:
            if raised:
                existing = await redis.hget(redis_key, user_id)
                if existing:
                    try:
                        state = json.loads(existing.decode())
                    except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
                        state = None
                else:
                    state = None
                if not state:
                    state = {
                        "raised": True,
                        "raised_at": int(time.time()),
                        "display_name": user.profile.get("display_name") or "",
                    }
                else:
                    state["raised"] = True
                    state["display_name"] = user.profile.get("display_name") or ""
                await redis.hset(redis_key, user_id, json.dumps(state))
                await redis.expire(redis_key, 3600 * 24)
                return state

            await redis.hdel(redis_key, user_id)
            await redis.expire(redis_key, 3600 * 24)
            return {
                "raised": False,
                "raised_at": None,
                "display_name": user.profile.get("display_name") or "",
            }

    async def _raised_hands(self, room_id):
        async with aredis(self._raise_hands_key(room_id)) as redis:
            raw_hands = await redis.hgetall(self._raise_hands_key(room_id))

        hands = []
        for raw_user_id, raw_state in raw_hands.items():
            try:
                state = json.loads(raw_state.decode())
            except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
                continue
            if not state.get("raised"):
                continue
            hands.append(
                {
                    "user": raw_user_id.decode(),
                    "raised": True,
                    "raised_at": state.get("raised_at"),
                    "display_name": state.get("display_name") or "",
                }
            )
        return sorted(hands, key=lambda hand: hand.get("raised_at") or 0)

    async def _get_raise_hand_target(self, user_id):
        user_id = str(user_id or self.consumer.user.pk)
        try:
            user_pk = int(user_id)
        except (TypeError, ValueError):
            raise ConsumerException("janus.target_not_found", "Participant not found.")

        try:
            return await database_sync_to_async(User.objects.get)(
                event=self.consumer.event,
                pk=user_pk,
            )
        except User.DoesNotExist:
            raise ConsumerException("janus.target_not_found", "Participant not found.")

    async def _remove_pending_admission(self, user_id, *, status):
        user_id = str(user_id)
        async with aredis(self._waiting_room_key(self.room.pk)) as redis:
            await redis.hdel(self._waiting_room_key(self.room.pk), user_id)
            await redis.expire(
                self._waiting_room_key(self.room.pk), self.WAITING_ROOM_TTL
            )

        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            {
                "type": "januscall.waiting_room_updated",
                "room": str(self.room.pk),
                "action": status,
                "user": {"id": user_id},
            },
        )

    async def _get_waiting_user(self, user_id):
        user_id = str(user_id or "")
        if not user_id:
            raise ConsumerException(
                "janus.waiting_room.not_found", "User is not waiting."
            )

        async with aredis(self._waiting_room_key(self.room.pk)) as redis:
            raw_user = await redis.hget(self._waiting_room_key(self.room.pk), user_id)
        if not raw_user:
            raise ConsumerException(
                "janus.waiting_room.not_found", "User is not waiting."
            )

        try:
            user_pk = int(user_id)
        except (TypeError, ValueError):
            raise ConsumerException(
                "janus.waiting_room.not_found", "User is not waiting."
            )

        try:
            return await database_sync_to_async(User.objects.get)(
                event=self.consumer.event,
                pk=user_pk,
            )
        except User.DoesNotExist:
            await self._remove_pending_admission(user_id, status="removed")
            raise ConsumerException(
                "janus.waiting_room.not_found", "User is not waiting."
            )

    async def _get_or_create_janus_room(self, redis_key, audiobridge=False, user=None):
        user = user or self.consumer.user
        display_name = (
            (user.profile or {}).get("display_name")
            or getattr(user, "fullname", None)
            or (user.email.split("@")[0] if getattr(user, "email", None) else None)
            or "Attendee"
        )
        if hasattr(user, "profile") and isinstance(user.profile, dict):
            if not user.profile.get("display_name"):
                user.profile["display_name"] = display_name
        elif not getattr(user, "profile", None):
            user.profile = {"display_name": display_name}

        cache_key = f"januscall:{redis_key}"
        user_secret_token = hashlib.sha256(
            f"januscall:usersecret:{settings.SECRET_KEY}:{user.pk}".encode()
        ).hexdigest()
        async with aredis() as redis:
            async with Lock(
                redis,
                name=f"januscall:lock:{redis_key}",
                timeout=90,
                blocking_timeout=90,
            ):
                room_data = await redis.get(cache_key)

                if room_data:
                    try:
                        room_data = json.loads(room_data.decode())
                        server = await database_sync_to_async(
                            JanusServer.objects.filter(active=True).get
                        )(url=room_data["server"])
                        if room_data.get("audiobridge", False) != audiobridge:
                            room_data = None
                        elif not await videoroom_add_token_if_exists(
                            server,
                            room_data,
                            user_secret_token,
                            audiobridge=room_data.get("audiobridge", False),
                        ):
                            room_data = None
                    except (JanusServer.DoesNotExist, KeyError, json.JSONDecodeError):
                        await redis.delete(cache_key)
                        room_data = None
                    except JanusError as e:
                        await redis.delete(cache_key)
                        room_data = None
                        if settings.SENTRY_DSN:
                            capture_exception(e)

                    if room_data is None:
                        await redis.delete(cache_key)

                if not room_data:
                    janus_server, turn_server = await self._servers()
                    room_data = await self._create_janus_room(
                        janus_server, audiobridge, user_secret_token
                    )
                    await redis.setex(cache_key, 3600 * 24, json.dumps(room_data))
                else:
                    await redis.expire(cache_key, 3600 * 24)
                    turn_server = await database_sync_to_async(turn.choose_server)(
                        self.consumer.event
                    )

            audio_user_id, video_user_id, screenshare_user_id = (
                await self._reserve_janus_user_ids(redis, 3, user=user)
            )
            await self._register_feed_ids(
                redis,
                self.room.pk,
                [
                    audio_user_id,
                    video_user_id,
                    screenshare_user_id,
                ],
                user=user,
            )

        iceServers = turn_server.get_ice_servers() if turn_server else []
        return {
            "token": user_secret_token,
            "sessionId": audio_user_id,
            "audioSessionId": audio_user_id,
            "videoSessionId": video_user_id,
            "screenShareSessionId": screenshare_user_id,
            "server": room_data["server"],
            "roomId": room_data["roomId"],
            "iceServers": iceServers,
        }

    async def _register_feed_ids(self, redis, room_id, feed_ids, user=None):
        user = user or self.consumer.user
        user_id = str(user.pk)
        user_feeds_key = self._room_user_feeds_key(room_id, user_id)
        for feed_id in feed_ids:
            normalized_feed_id = str(feed_id).split("_")[0]
            await redis.setex(
                self._room_feed_user_key(room_id, normalized_feed_id),
                3600 * 24,
                user_id,
            )
            await redis.sadd(user_feeds_key, normalized_feed_id)
            await redis.sadd(self._room_feeds_key(room_id), normalized_feed_id)
        await redis.expire(user_feeds_key, 3600 * 24)
        await redis.expire(self._room_feeds_key(room_id), 3600 * 24)

    async def _can_moderate_room(self):
        return await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=[
                Permission.ROOM_JANUSCALL_MODERATE,
                Permission.ROOM_UPDATE,
                Permission.EVENT_UPDATE,
            ],
            room=self.room,
        )

    async def _room_data_for_moderation(self):
        cache_key = f"januscall:room:{self.room.pk}"
        async with aredis(cache_key) as redis:
            raw_room_data = await redis.get(cache_key)

        if not raw_room_data:
            raise ConsumerException("janus.not_found", "Janus room not found.")

        try:
            room_data = json.loads(raw_room_data.decode())
            server = await database_sync_to_async(
                JanusServer.objects.filter(active=True).get
            )(url=room_data["server"])
        except (JanusServer.DoesNotExist, KeyError, json.JSONDecodeError):
            raise ConsumerException("janus.not_found", "Janus room not found.")

        return server, room_data

    async def _resolve_target_user(self, room_id, feed_id):
        normalized_feed_id = str(feed_id or "").split("_")[0]
        if not normalized_feed_id:
            raise ConsumerException("janus.target_not_found", "Participant not found.")

        async with aredis() as redis:
            raw_user_id = await redis.get(
                self._room_feed_user_key(room_id, normalized_feed_id)
            )
            if not raw_user_id:
                raw_user_id = await redis.get(f"januscall:user:{normalized_feed_id}")
            if not raw_user_id:
                raise ConsumerException(
                    "janus.target_not_found", "Participant not found."
                )
            user_id = raw_user_id.decode()
            raw_feed_ids = await redis.smembers(self._room_user_feeds_key(room_id, user_id))

        feed_ids = [feed.decode() for feed in raw_feed_ids]
        if normalized_feed_id not in feed_ids:
            feed_ids.append(normalized_feed_id)
        return user_id, normalized_feed_id, feed_ids

    async def _moderate_participant(
        self, body, *, action, janus_moderation=None, kick=False
    ):
        if not await self._can_moderate_room():
            raise ConsumerException("protocol.denied", "Permission denied.")

        target_user_id, target_feed_id, target_feed_ids = await self._resolve_target_user(
            self.room.pk, body.get("target_feed_id")
        )
        try:
            server, room_data = await self._room_data_for_moderation()
            if kick and target_feed_ids:
                await self._kick_feed_ids(server, room_data, target_feed_ids)
            elif not kick:
                await videoroom_moderate(
                    server,
                    room_data,
                    target_feed_id,
                    **(janus_moderation or {}),
                )
        except JanusError as e:
            self._capture_janus_exception(e)
        except ConsumerException:
            pass

        payload = {
            "type": "januscall.moderation_action",
            "room": str(self.room.pk),
            "action": action,
            "target_user": target_user_id,
            "target_feed_id": target_feed_id,
            "moderator": str(self.consumer.user.pk),
        }
        await self.consumer.send_success(
            {
                "action": action,
                "target_user": target_user_id,
                "target_feed_id": target_feed_id,
            }
        )
        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            payload,
        )

    async def _room_feed_ids(self, room_id):
        async with aredis() as redis:
            raw_feed_ids = await redis.smembers(self._room_feeds_key(room_id))
        return [feed_id.decode() for feed_id in raw_feed_ids]

    async def _kick_feed_ids(self, server, room_data, feed_ids):
        for feed_id in feed_ids:
            try:
                await videoroom_kick(server, room_data, feed_id)
            except JanusError as e:
                self._capture_janus_exception(e)

    async def _end_meeting_for_all(self):
        if not await self._can_moderate_room():
            raise ConsumerException("protocol.denied", "Permission denied.")

        try:
            server, room_data = await self._room_data_for_moderation()
            await self._kick_feed_ids(
                server,
                room_data,
                await self._room_feed_ids(self.room.pk),
            )
        except ConsumerException:
            pass

        payload = {
            "type": "januscall.moderation_action",
            "room": str(self.room.pk),
            "action": "end_meeting",
            "moderator": str(self.consumer.user.pk),
        }
        await self.consumer.send_success({"action": "end_meeting"})
        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            payload,
        )

    async def _create_janus_room(self, janus_server, audiobridge, user_secret_token):
        for attempt in range(3):
            try:
                return await create_videoroom(
                    janus_server,
                    room_id=self._new_janus_room_id(),
                    audiobridge=audiobridge,
                    init_token=user_secret_token,
                )
            except JanusPluginError as e:
                if "already exists" in str(e).lower() and attempt < 2:
                    continue
                self._capture_janus_exception(e)
                raise ConsumerException("janus.failed", "Could not create a video session")
            except JanusError as e:
                self._capture_janus_exception(e)
                raise ConsumerException("janus.failed", "Could not create a video session")

        raise ConsumerException("janus.failed", "Could not create a video session")

    @staticmethod
    def _new_janus_room_id():
        return secrets.randbelow(2_147_483_647) + 1

    async def _reserve_janus_user_ids(self, redis, count, user=None):
        target_user = user or self.consumer.user
        user_ids = []
        user_pk = str(target_user.pk)
        attempts = 0

        while len(user_ids) < count and attempts < 100:
            attempts += 1
            user_id = self._new_janus_room_id()
            if user_id in user_ids:
                continue

            reserved = await redis.set(
                f"januscall:user:{user_id}",
                user_pk,
                ex=3600 * 24,
                nx=True,
            )
            if reserved:
                user_ids.append(user_id)

        if len(user_ids) != count:
            raise ConsumerException("janus.failed", "Could not allocate video session ids")

        return user_ids

    @staticmethod
    def _capture_janus_exception(exception):
        if settings.SENTRY_DSN:
            capture_exception(exception)

    @command("identify")
    @require_event_permission(Permission.EVENT_VIEW)
    async def identify(self, body):
        async with aredis() as redis:
            sessionid = str(body.get("id", "")).split("_")[0]
            userid = await redis.get(f"januscall:user:{sessionid}")
            if userid:
                user = await get_public_user(
                    self.consumer.event.id,
                    userid.decode(),
                    include_admin_info=await self.consumer.event.has_permission_async(
                        user=self.consumer.user,
                        permission=Permission.EVENT_USERS_MANAGE,
                    ),
                    trait_badges_map=self.consumer.event.config.get("trait_badges_map"),
                )
                if user:
                    await self.consumer.send_success(user)
                    return
        await self.consumer.send_error(code="user.not_found")

    @event("media_state")
    async def push_media_state(self, body):
        await self.consumer.send_json(
            [
                body["type"],
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("moderation_action")
    async def push_moderation_action(self, body):
        await self.consumer.send_json(
            [
                body["type"],
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("waiting_room_updated")
    async def push_waiting_room_updated(self, body):
        await self.consumer.send_json(
            [
                body["type"],
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("spotlight")
    async def push_spotlight(self, body):
        await self.consumer.send_json(
            [
                body["type"],
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("raise_hand")
    async def push_raise_hand(self, body):
        await self.consumer.send_json(
            [
                body["type"],
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("raise_hand_notification")
    async def push_raise_hand_notification(self, body):
        await self.consumer.send_json(
            [
                body["type"],
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("admission_result")
    async def push_admission_result(self, body):
        self.waiting_admission_rooms.pop(str(body.get("room")), None)
        await self.consumer.send_json(
            [
                body["type"],
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    async def dispatch_disconnect(self, close_code):
        for room in list(self.waiting_admission_rooms.values()):
            self.room = room
            await self._remove_pending_admission(
                self.consumer.user.pk, status="cancelled"
            )
            self.waiting_admission_rooms.pop(str(room.pk), None)
            del self.room

        for room in list(self.media_state_rooms.values()):
            await self.cleanup_media_state_for_room(room)

        for room in list(self.raise_hand_rooms.values()):
            await self.cleanup_raise_hand_for_room(room)
