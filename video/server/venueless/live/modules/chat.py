import functools
import logging
import re
from contextlib import suppress

import asgiref
from sentry_sdk import configure_scope

from venueless.core.permissions import Permission
from venueless.core.services.chat import ChatService, get_channel
from venueless.core.utils.redis import aioredis
from venueless.live.channels import GROUP_CHAT, GROUP_USER
from venueless.live.decorators import (
    command,
    event,
    require_world_permission,
    room_action,
)
from venueless.live.exceptions import ConsumerException
from venueless.live.modules.base import BaseModule
from venueless.storage.tasks import retrieve_preview_information

logger = logging.getLogger(__name__)


def channel_action(
    room_permission_required: Permission = None,
    room_module_required=None,
    require_membership=True,
):
    """
    Wraps a command that works on a chat channel regardless of whether the channel is tied to a room or not.
    If it *is* tied to a room, the ``room_permisison_required`` and ``room_module_required`` options are enforced.

    ``require_membership`` enforces the user is a member of a channel for an action.
    """

    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(self, body, *args):
            if "channel" in body:
                self.channel = self.consumer.channel_cache.get(body["channel"])
                if not self.channel:
                    self.channel = await get_channel(
                        world=self.consumer.world, pk=body["channel"]
                    )
                    self.consumer.channel_cache[body["channel"]] = self.channel
                elif self.channel.room:
                    await self.channel.room.refresh_from_db_if_outdated()
            else:
                raise ConsumerException("chat.unknown", "Unknown channel ID")
            if not self.channel:
                raise ConsumerException("room.unknown", "Unknown room ID")

            if self.channel.room and room_module_required is not None:
                module_config = [
                    m.get("config", {})
                    for m in self.channel.room.module_config
                    if m["type"] == room_module_required
                ]
                if module_config:
                    self.module_config = module_config[0]
                else:
                    raise ConsumerException(
                        "room.unknown", "Room does not contain a matching module."
                    )

            if not getattr(self.consumer, "user", None):  # pragma: no cover
                # Just a precaution, should never be called since MainConsumer.receive_json already checks this
                raise ConsumerException(
                    "protocol.unauthenticated", "No authentication provided."
                )

            if self.channel.room and room_permission_required is not None:
                if not await self.consumer.world.has_permission_async(
                    user=self.consumer.user,
                    permission=room_permission_required,
                    room=self.channel.room,
                ):
                    raise ConsumerException("protocol.denied", "Permission denied.")

            req_m = (
                require_membership(self.channel)
                if callable(require_membership)
                else require_membership
            )
            if req_m:
                if not await self.consumer.user.is_member_of_channel_async(
                    self.channel.pk
                ):
                    raise ConsumerException("chat.denied")

            try:
                return await func(self, body, *args)
            finally:
                del self.channel

        return wrapped

    return wrapper


class ChatModule(BaseModule):
    prefix = "chat"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_id = None
        self.channels_subscribed = set()
        self.service = ChatService(self.consumer.world)

    async def _subscribe(self):
        self.channels_subscribed.add(self.channel)
        await self.consumer.channel_layer.group_add(
            GROUP_CHAT.format(channel=self.channel_id), self.consumer.channel_name
        )
        await self.service.track_subscription(
            self.channel_id, self.consumer.user.id, self.consumer.socket_id
        )
        last_id = await self.service.get_last_id()
        return {
            "state": None,
            "next_event_id": (last_id) + 1,
            "notification_pointer": await self.service.get_highest_nonmember_id_in_channel(
                self.channel_id
            ),
            "members": await self.service.get_channel_users(
                self.channel_id,
                include_admin_info=await self.consumer.world.has_permission_async(
                    user=self.consumer.user, permission=Permission.WORLD_USERS_MANAGE
                ),
            ),
        }

    async def _unsubscribe(self, clean_volatile_membership=True):
        with suppress(KeyError):
            self.channels_subscribed.remove(self.channel)
        if clean_volatile_membership:
            remaining_sockets = await self.service.track_unsubscription(
                self.channel_id, self.consumer.user.id, self.consumer.socket_id
            )
            if remaining_sockets == 0 and await self.service.membership_is_volatile(
                self.channel_id, self.consumer.user.id
            ):
                await self._leave()
        await self.consumer.channel_layer.group_discard(
            GROUP_CHAT.format(channel=self.channel_id), self.consumer.channel_name
        )

    @command("subscribe")
    @channel_action(
        room_permission_required=Permission.ROOM_CHAT_READ,
        room_module_required="chat.native",
        require_membership=lambda channel: not channel.room,
    )
    async def subscribe(self, body):
        reply = await self._subscribe()
        await self.consumer.send_success(reply)

    @command("join")
    @room_action(
        permission_required=Permission.ROOM_CHAT_JOIN, module_required="chat.native"
    )
    async def join(self, body):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("channel.join.missing_profile")
        reply = await self._subscribe()

        volatile_config = self.module_config.get("volatile", False)
        volatile_client = body.get("volatile", volatile_config)
        if (
            volatile_client != volatile_config
            and await self.consumer.world.has_permission_async(
                user=self.consumer.user,
                room=self.room,
                permission=Permission.ROOM_CHAT_MODERATE,
            )
        ):
            volatile_config = volatile_client

        joined = await self.service.add_channel_user(
            self.channel_id, self.consumer.user, volatile=volatile_config
        )
        if joined:
            event = await self.service.create_event(
                channel=self.channel,
                event_type="channel.member",
                content={
                    "membership": "join",
                    "user": self.consumer.user.serialize_public(
                        trait_badges_map=self.consumer.world.config.get(
                            "trait_badges_map"
                        )
                    ),
                },
                sender=self.consumer.user,
            )
            await self.consumer.channel_layer.group_send(
                GROUP_CHAT.format(channel=self.channel_id),
                event,
            )
            await self.service.broadcast_channel_list(
                self.consumer.user, self.consumer.socket_id
            )
            if not volatile_config:
                async with aioredis() as redis:
                    await redis.sadd(
                        f"chat:unread.notify:{self.channel_id}",
                        str(self.consumer.user.id),
                    )
        await self.consumer.send_success(reply)

    async def _leave(self):
        await self.service.remove_channel_user(self.channel_id, self.consumer.user.id)
        await self.consumer.channel_layer.group_send(
            GROUP_CHAT.format(channel=self.channel_id),
            await self.service.create_event(
                channel=self.channel,
                event_type="channel.member",
                content={
                    "membership": "leave",
                    "user": self.consumer.user.serialize_public(
                        trait_badges_map=self.consumer.world.config.get(
                            "trait_badges_map"
                        )
                    ),
                },
                sender=self.consumer.user,
            ),
        )
        await self.service.broadcast_channel_list(
            self.consumer.user, self.consumer.socket_id
        )

    @command("leave")
    @channel_action(
        room_module_required="chat.native",
        require_membership=lambda channel: not channel.room,
    )
    async def leave(self, body):
        await self._unsubscribe(clean_volatile_membership=False)
        if self.channel.room:
            await self._leave()
            async with aioredis() as redis:
                await redis.srem(
                    f"chat:unread.notify:{self.channel_id}", str(self.consumer.user.id)
                )
        else:
            await self.service.hide_channel_user(self.channel_id, self.consumer.user.id)
            async with aioredis() as redis:
                await redis.delete(f"chat:direct:shownall:{self.channel_id}")
            await self.service.broadcast_channel_list(
                self.consumer.user, self.consumer.socket_id
            )

        await self.consumer.send_success()

    @command("unsubscribe")
    @channel_action(room_module_required="chat.native", require_membership=False)
    async def unsubscribe(self, body):
        await self._unsubscribe()
        await self.consumer.send_success()

    @command("fetch")
    @channel_action(
        room_permission_required=Permission.ROOM_CHAT_READ,
        room_module_required="chat.native",
        require_membership=lambda channel: not channel.room,
    )
    async def fetch(self, body):
        count = body["count"]
        before_id = body["before_id"]
        volatile_config = self.channel.room and (
            self.module_config.get("volatile", False) or self.channel.room.force_join
        )
        events = await self.service.get_events(
            self.channel_id,
            before_id=before_id,
            count=count,
            skip_membership=volatile_config,
        )
        await self.consumer.send_success({"results": events})

    @command("mark_read")
    @channel_action(room_module_required="chat.native", require_membership=False)
    async def mark_read(self, body):
        if not body.get("id"):
            raise ConsumerException("chat.invalid_body")
        async with aioredis() as redis:
            await redis.hset(
                f"chat:read:{self.consumer.user.id}", self.channel_id, body.get("id")
            )
            await redis.sadd(
                f"chat:unread.notify:{self.channel_id}", str(self.consumer.user.id)
            )
        await self.consumer.send_success()
        await self.consumer.channel_layer.group_send(
            GROUP_USER.format(id=self.consumer.user.id),
            {
                "type": "chat.read_pointers",
                "socket": self.consumer.socket_id,
            },
        )

    @event("read_pointers")
    async def publish_read_pointers(self, body):
        if self.consumer.socket_id != body["socket"]:
            async with aioredis() as redis:
                redis_read = await redis.hgetall(f"chat:read:{self.consumer.user.id}")
                read_pointers = {
                    k.decode(): int(v.decode()) for k, v in redis_read.items()
                }
            await self.consumer.send_json(["chat.read_pointers", read_pointers])

    @event("notification_pointers")
    async def publish_notification_pointers(self, body):
        await self.consumer.send_json(["chat.notification_pointers", body.get("data")])

    @command("send")
    @channel_action(
        room_permission_required=Permission.ROOM_CHAT_SEND,
        room_module_required="chat.native",
        require_membership=True,
    )
    async def send(self, body):
        content = body["content"]
        event_type = body["event_type"]
        if event_type != "channel.message":
            raise ConsumerException("chat.unsupported_event_type")
        if not (
            content.get("type") == "text"
            or (content.get("type") == "deleted" and "replaces" in body)
            or (content.get("type") == "call" and not self.channel.room)
        ):
            raise ConsumerException("chat.unsupported_content_type")

        if body.get("replaces"):
            other_message = await self.service.get_event(
                pk=body["replaces"],
                channel_id=self.channel_id,
            )
            if self.consumer.user.id != other_message.sender_id:
                # Users may only edit messages by other users if they are mods,
                # and even then only delete them
                is_moderator = (
                    self.channel.room
                    and await self.consumer.world.has_permission_async(
                        user=self.consumer.user,
                        room=self.channel.room,
                        permission=Permission.ROOM_CHAT_MODERATE,
                    )
                )
                if body["content"]["type"] != "deleted" or not is_moderator:
                    raise ConsumerException("chat.denied")
            await self.service.update_event(
                other_message, new_content=content, by_user=self.consumer.user
            )

        if content.get("type") == "text" and not content.get("body"):
            raise ConsumerException("chat.empty")

        if await self.consumer.user.is_blocked_in_channel_async(self.channel):
            raise ConsumerException("chat.denied")

        if self.consumer.user.is_silenced:
            # In regular channels, this is already prevented by room permissions, but we need to check for DMs
            raise ConsumerException("chat.denied")

        # Re-open direct messages. If a user hid a direct message channel, it should re-appear once they get a message
        if not self.channel.room:
            async with aioredis() as redis:
                all_visible = await redis.exists(
                    f"chat:direct:shownall:{self.channel_id}"
                )
            if not all_visible:
                users = await self.service.show_channels_to_hidden_users(
                    self.channel_id
                )
                for user in users:
                    await self.service.broadcast_channel_list(
                        user, self.consumer.socket_id
                    )
                    async with aioredis() as redis:
                        await redis.sadd(
                            f"chat:unread.notify:{self.channel_id}",
                            str(user.id),
                        )
            async with aioredis() as redis:
                await redis.setex(
                    f"chat:direct:shownall:{self.channel_id}", 3600 * 24 * 7, "true"
                )

        event = await self.service.create_event(
            channel=self.channel,
            event_type=event_type,
            content=content,
            sender=self.consumer.user,
            replaces=body.get("replaces", None),
        )
        await self.consumer.send_success(
            {"event": {k: v for k, v in event.items() if k != "type"}}
        )
        await self.consumer.channel_layer.group_send(
            GROUP_CHAT.format(channel=self.channel_id), event
        )

        # Unread notifications
        # We pop user IDs from the list of users to notify, because once they've been notified they don't need a
        # notification again until they sent a new read pointer.
        async with aioredis() as redis:
            batch_size = 100
            while True:
                users = await redis.spop(f"chat:unread.notify:{self.channel_id}", 100)

                for user in users:
                    await self.consumer.channel_layer.group_send(
                        GROUP_USER.format(id=user.decode()),
                        {
                            "type": "chat.notification_pointers",
                            "data": {self.channel_id: event["event_id"]},
                        },
                    )

                if len(users) < batch_size:
                    break

        if content.get("type") == "text":
            match = re.search(r"(?P<url>https?://[^\s]+)", content.get("body"))
            if match:
                await asgiref.sync.sync_to_async(
                    retrieve_preview_information.apply_async
                )(
                    kwargs={
                        "world": str(self.consumer.world.id),
                        "event_id": event["event_id"],
                    }
                )

    @event("event", refresh_world=True, refresh_user=True)
    async def publish_event(self, body):
        channel = self.consumer.channel_cache.get(body["channel"])
        if channel:
            if channel.room:
                await channel.room.refresh_from_db_if_outdated()
        else:
            channel = await get_channel(world=self.consumer.world, id=body["channel"])
            self.consumer.channel_cache[body["channel"]] = channel

        if channel.room and not await self.consumer.world.has_permission_async(
            user=self.consumer.user,
            permission=Permission.ROOM_CHAT_READ,
            room=channel.room,
        ):
            return
        await self.consumer.send_json(
            ["chat.event", {k: v for k, v in body.items() if k != "type"}]
        )

    @command("direct.create")
    @require_world_permission(Permission.WORLD_CHAT_DIRECT)
    async def direct_create(self, body):
        user_ids = set(body.get("users", []))
        user_ids.add(self.consumer.user.id)

        hide = body.get("hide", True)

        channel, created, users = await self.service.get_or_create_direct_channel(
            user_ids=user_ids, hide=hide, hide_except=str(self.consumer.user.id)
        )
        if not channel:
            raise ConsumerException("chat.denied")

        self.channel_id = str(channel.id)
        self.channel = channel

        reply = await self._subscribe()
        if created:
            for user in users:
                event = await self.service.create_event(
                    channel=channel,
                    event_type="channel.member",
                    content={
                        "membership": "join",
                        "user": user.serialize_public(
                            trait_badges_map=self.consumer.world.config.get(
                                "trait_badges_map"
                            )
                        ),
                    },
                    sender=user,
                )
                await self.consumer.channel_layer.group_send(
                    GROUP_CHAT.format(channel=self.channel_id),
                    event,
                )

                if not hide or user == self.consumer.user:
                    await self.service.broadcast_channel_list(
                        user=user, socket_id=self.consumer.socket_id
                    )
                    async with aioredis() as redis:
                        await redis.sadd(
                            f"chat:unread.notify:{self.channel_id}",
                            str(user.id),
                        )
            if not hide:
                async with aioredis() as redis:
                    await redis.setex(
                        f"chat:direct:shownall:{self.channel_id}", 3600 * 24 * 7, "true"
                    )

        reply["id"] = str(channel.id)
        await self.consumer.send_success(reply)

    async def dispatch_command(self, content):
        self.channel_id = content[2].get("channel")
        with configure_scope() as scope:
            scope.set_extra("last_channel", str(self.channel_id))
        return await super().dispatch_command(content)

    async def dispatch_disconnect(self, close_code):
        for channel in frozenset(self.channels_subscribed):
            self.channel = channel
            self.channel_id = channel.pk
            await self._unsubscribe()
