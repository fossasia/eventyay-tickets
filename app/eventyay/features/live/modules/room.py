import asyncio
import ipaddress
import logging
import secrets
import socket
import time
from datetime import timedelta
from urllib.parse import urljoin, urlparse

import asgiref.sync
import requests as http_requests
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from requests import RequestException
from sentry_sdk import add_breadcrumb, configure_scope

from eventyay.base.models.room import AnonymousInvite, RoomConfigSerializer
from eventyay.base.services.event import (
    create_room,
    get_room_config_for_user,
    get_rooms,
    is_chat_channel_room,
    notify_event_change,
)
from eventyay.base.services.poll import get_polls, get_voted_polls
from eventyay.base.services.reactions import store_reaction
from eventyay.base.services.room import (
    delete_room,
    end_view,
    get_viewers,
    normalize_after_priority_change,
    reorder_rooms,
    save_room,
    start_view,
    validate_room_config_patch,
)
from eventyay.base.services.room_creation_gate import (
    newly_added_server_backed_room_modules,
    user_can_create_server_backed_room_during_development,
    user_has_all_server_backed_room_create_permissions,
)
from eventyay.core.permissions import Permission
from eventyay.core.utils.redis import aredis
from eventyay.features.live.channels import (
    GROUP_EVENT,
    GROUP_ROOM,
    GROUP_ROOM_POLL_ALL_RESULTS,
    GROUP_ROOM_POLL_MANAGE,
    GROUP_ROOM_POLL_READ,
    GROUP_ROOM_POLL_RESULTS,
    GROUP_ROOM_QUESTION_MODERATE,
    GROUP_ROOM_QUESTION_READ,
    GROUP_ROOM_VIEWERS,
)
from eventyay.features.live.decorators import (
    command,
    event,
    require_event_permission,
    room_action,
)
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


logger = logging.getLogger(__name__)


def serialize_room_config(room_or_rooms, many=False):
    data = RoomConfigSerializer(room_or_rooms, many=many).data
    _strip_jitsi_secrets(data, many=many)
    return data


def _strip_jitsi_secrets(data, many=False):
    rooms = data if many else [data]
    for room in rooms:
        for module in room.get("module_config") or []:
            if module.get("type") != "call.jitsi":
                continue
            config = module.get("config")
            if isinstance(config, dict):
                for key in ("domain", "jwt_enabled", "app_id", "key_id", "app_secret"):
                    config.pop(key, None)


class RoomModule(BaseModule):
    prefix = "room"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_views = {}

    def _room_from_viewer_event(self, body):
        room_id = str(body.get("_room"))
        for room in self.current_views:
            if str(room.pk) == room_id:
                return room
        return None

    @staticmethod
    def _is_private_url(url):
        """Check if a URL points to a private/localhost address (SSRF protection)."""
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return True
        try:
            for info in socket.getaddrinfo(hostname, None):
                addr = info[4][0]
                if not ipaddress.ip_address(addr).is_global:
                    return True
        except (socket.gaierror, ValueError):
            return True
        return False

    async def _verify_webhook_challenges(self, old_module_config, new_module_config):
        """
        When module_config is updated, verify any new webhook URLs via
        challenge-response before allowing them to be saved.
        """
        old_urls = {}
        for m in old_module_config:
            cfg = m.get("config", {})
            url = cfg.get("webhook_url")
            if url:
                old_urls[m["type"]] = url

        for m in new_module_config:
            cfg = m.get("config", {})
            url = cfg.get("webhook_url")
            secret = cfg.get("webhook_hmac_secret")
            if secret and not url:
                cfg.pop("webhook_hmac_secret", None)
                secret = None
            if not url:
                continue
            # Always validate secret when URL is set (not just on URL change)
            if not secret:
                raise ConsumerException(
                    "webhook.missing_secret",
                    "webhook_hmac_secret is required when webhook_url is set.",
                )
            # Validate URL structure
            parsed = urlparse(url)
            scheme = (parsed.scheme or "").lower()
            if scheme not in ("https", "http"):
                raise ConsumerException(
                    "webhook.invalid_url",
                    "Webhook URL must use http or https.",
                )
            if scheme != "https" and not settings.DEBUG:
                raise ConsumerException(
                    "webhook.insecure_url",
                    "Webhook URL must use HTTPS in production.",
                )
            if parsed.fragment or parsed.username or parsed.password:
                raise ConsumerException(
                    "webhook.invalid_url",
                    "Webhook URL must not contain fragments or credentials.",
                )
            # Block private/localhost targets (SSRF protection), skip in DEBUG
            if not settings.DEBUG:
                is_private = await asgiref.sync.sync_to_async(
                    self._is_private_url
                )(url)
                if is_private:
                    raise ConsumerException(
                        "webhook.invalid_url",
                        "Webhook URL must not point to a private network address.",
                    )
            # Only run challenge verification if the URL is new or changed
            if old_urls.get(m["type"]) == url:
                continue
            # Challenge verification
            challenge_token = secrets.token_urlsafe(32)
            try:
                resp = await asgiref.sync.sync_to_async(http_requests.get)(
                    url,
                    params={"challenge": challenge_token},
                    timeout=5,
                    allow_redirects=False,
                )
            except RequestException:
                raise ConsumerException(
                    "webhook.verification_failed",
                    "Could not reach webhook URL for challenge verification.",
                )
            if resp.status_code != 200:
                raise ConsumerException(
                    "webhook.verification_failed",
                    f"Webhook challenge returned HTTP {resp.status_code}.",
                )
            try:
                data = resp.json()
            except ValueError:
                raise ConsumerException(
                    "webhook.verification_failed",
                    "Webhook challenge response is not valid JSON.",
                )
            if data.get("challenge") != challenge_token:
                raise ConsumerException(
                    "webhook.verification_failed",
                    "Webhook challenge token mismatch.",
                )

    @command("enter")
    @room_action(permission_required=Permission.ROOM_VIEW)
    async def enter_room(self, body):
        await self.consumer.channel_layer.group_add(
            GROUP_ROOM.format(id=self.room.pk), self.consumer.channel_name
        )
        permissions = {
            Permission.ROOM_QUESTION_READ: GROUP_ROOM_QUESTION_READ,
            Permission.ROOM_QUESTION_MODERATE: GROUP_ROOM_QUESTION_MODERATE,
            Permission.ROOM_POLL_EARLY_RESULTS: GROUP_ROOM_POLL_ALL_RESULTS,
            Permission.ROOM_POLL_READ: GROUP_ROOM_POLL_READ,
            Permission.ROOM_POLL_MANAGE: GROUP_ROOM_POLL_MANAGE,
        }
        for permission, group_name in permissions.items():
            if await self.consumer.event.has_permission_async(
                user=self.consumer.user,
                room=self.room,
                permission=permission,
            ):
                await self.consumer.channel_layer.group_add(
                    group_name.format(id=self.room.pk),
                    self.consumer.channel_name,
                )

        if await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            room=self.room,
            permission=Permission.ROOM_POLL_VOTE,
        ):
            # For polls, we have to add users to all groups they have already voted for
            voted_polls = await get_voted_polls(self.room, self.consumer.user)
            for poll in voted_polls:
                await self.consumer.channel_layer.group_add(
                    GROUP_ROOM_POLL_RESULTS.format(id=self.room.pk, poll=poll),
                    self.consumer.channel_name,
                )

        self.current_views[self.room], actual_view_count = await start_view(
            self.room,
            self.consumer.user,
            delete=not self.consumer.event.config.get("track_room_views", True),
        )
        await self._update_view_count(self.room, actual_view_count)

        await get_channel_layer().group_send(
            GROUP_ROOM_VIEWERS.format(id=self.room.pk),
            {
                "type": "room.viewer.added",
                "user": self.consumer.user.serialize_public(
                    trait_badges_map=self.consumer.event.config.get(
                        "trait_badges_map"
                    )
                ),
                "_show_publicly": bool(self.consumer.user.show_publicly),
                "_room": str(self.room.pk),
            },
        )

        data = {}

        if await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            room=self.room,
            permission=Permission.ROOM_VIEWERS,
        ):
            await self.consumer.channel_layer.group_add(
                GROUP_ROOM_VIEWERS.format(id=self.room.pk),
                self.consumer.channel_name,
            )
            data["viewers"] = await get_viewers(
                self.consumer.event,
                self.room,
                # Anyone allowed to see the viewer list (incl. kiosk displays)
                # should see all people currently in the room.
                include_private=True,
            )

        await self.consumer.send_success(data)

        if settings.SENTRY_DSN:
            add_breadcrumb(
                category="room",
                message=f"Entered room {self.room.pk} ({self.room.name})",
                level="info",
            )
            with configure_scope() as scope:
                scope.set_extra("last_room", str(self.room.pk))

    async def _leave_room(self, room):
        group_names = [
            GROUP_ROOM,
            GROUP_ROOM_QUESTION_MODERATE,
            GROUP_ROOM_QUESTION_READ,
            GROUP_ROOM_POLL_MANAGE,
            GROUP_ROOM_POLL_READ,
            GROUP_ROOM_VIEWERS,
        ]
        for group_name in group_names:
            await self.consumer.channel_layer.group_discard(
                group_name.format(id=room.pk), self.consumer.channel_name
            )
        for poll in await get_polls(room):
            await self.consumer.channel_layer.group_discard(
                GROUP_ROOM_POLL_RESULTS.format(id=room.pk, poll=poll["id"]),
                self.consumer.channel_name,
            )
        if room in self.current_views:
            actual_view_count, is_last = await end_view(
                self.current_views[room],
                delete=not self.consumer.event.config.get("track_room_views", True),
            )
            del self.current_views[room]
            await self._update_view_count(room, actual_view_count)
            if is_last:
                await get_channel_layer().group_send(
                    GROUP_ROOM_VIEWERS.format(id=room.pk),
                    {
                        "type": "room.viewer.removed",
                        "user_id": str(self.consumer.user.id),
                        "_show_publicly": bool(self.consumer.user.show_publicly),
                        "_room": str(room.pk),
                    },
                )

    async def _update_view_count(self, room, actual_view_count):
        if is_chat_channel_room(room):
            return
        async with aredis(f"room:approxcount:known:{room.pk}") as redis:
            prev_value = await redis.getset(
                f"room:approxcount:known:{room.pk}", actual_view_count
            )
            is_changed = True
            if prev_value is not None:
                try:
                    is_changed = int(prev_value) != actual_view_count
                except (ValueError, TypeError):
                    is_changed = True
            if is_changed:
                await redis.expire(f"room:approxcount:known:{room.pk}", 900)
                await self.consumer.channel_layer.group_send(
                    GROUP_EVENT.format(id=self.consumer.event.pk),
                    {
                        "type": "event.user_count_change",
                        "room": str(room.pk),
                        "users": actual_view_count,
                    },
                )

    @command("leave")
    @room_action()
    async def leave_room(self, body):
        await self._leave_room(self.room)
        await self.consumer.send_success({})

    async def dispatch_disconnect(self, close_code):
        for room in list(self.current_views.keys()):
            await self._leave_room(room)

    @command("react")
    @room_action(permission_required=Permission.ROOM_VIEW)
    async def send_reaction(self, body):
        reaction = body.get("reaction")
        if reaction not in (
            "👏",
            "❤️",
            "👍",
            "🤣",
            "😮",
        ):
            raise ConsumerException(
                code="room.unknown_reaction", message="Unknown reaction"
            )

        redis_key = f"reactions:{self.consumer.event.id}:{body['room']}"
        redis_debounce_key = f"reactions:{self.consumer.event.id}:{body['room']}:{reaction}:{self.consumer.user.id}"

        # We want to send reactions out to anyone, but we want to aggregate them over short time frames ("ticks") to
        # make sure we do not send 500 messages if 500 people react in the same second, but just one.
        async with aredis(redis_debounce_key) as redis:
            debounce = await redis.set(
                redis_debounce_key,
                "1",
                ex=2,
                nx=True,
            )
            if not debounce:
                # User reacted in the 2 seconds, let's ignore this.
                await self.consumer.send_success({})
                return

        async with aredis(redis_key) as redis:
            # First, increase the number of reactions
            tr = redis.pipeline(transaction=True)
            tr.hsetnx(redis_key, "tick", int(time.time()))
            tr.hget(redis_key, "tick")
            tr.hincrby(redis_key, reaction, 1)
            tick_new, tick_start, _ = await tr.execute()

            await self.consumer.send_success({})

            if tick_new or time.time() - int(tick_start.decode()) > 3:
                # We're the first one to react since the last tick! It's our job to wait for the length of a tick, then
                # distribute the value to everyone.
                await asyncio.sleep(1)

                tr = redis.pipeline(transaction=True)
                tr.hgetall(redis_key)
                tr.delete(redis_key)
                val, _ = await tr.execute()
                if not val:
                    return
                await self.consumer.channel_layer.group_send(
                    GROUP_ROOM.format(id=self.room.pk),
                    {
                        "type": "room.reaction",
                        "reactions": {
                            k.decode(): int(v.decode())
                            for k, v in val.items()
                            if k.decode() != "tick"
                        },
                        "room": str(body["room"]),
                    },
                )
                for k, v in val.items():
                    if k.decode() != "tick":
                        await store_reaction(body["room"], k.decode(), int(v.decode()))
            # else: We're just contributing to the reaction counter that someone else started.

    @command("create")
    @require_event_permission(
        [
            Permission.EVENT_ROOMS_CREATE_STAGE,
            Permission.EVENT_ROOMS_CREATE_BBB,
            Permission.EVENT_ROOMS_CREATE_JITSI,
            Permission.EVENT_ROOMS_CREATE_CHAT,
            Permission.ROOM_UPDATE,
        ]
    )
    async def create_room(self, body):
        try:
            room = await create_room(self.consumer.event, body, self.consumer.user)
        except ValidationError as e:
            await self.consumer.send_error(
                code=f"room.invalid.{e.code}", message=str(e)
            )
        else:
            await self.consumer.send_success(room)

    @event("reaction")
    async def push_reaction(self, body):
        await self.consumer.send_json(
            [
                body["type"],
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("viewer.added")
    async def push_viewer_added(self, body):
        room = self._room_from_viewer_event(body)
        if not body.get("_show_publicly", True):
            can_view_private = await self.consumer.event.has_permission_async(
                user=self.consumer.user,
                room=room,
                permission=Permission.ROOM_VIEWERS,
            ) or await self.consumer.event.has_organizer_role_async(
                user=self.consumer.user,
                room=room,
            )
            if not can_view_private:
                return
        await self.consumer.send_json(
            [
                body["type"],
                {
                    k: v
                    for k, v in body.items()
                    if k != "type" and not k.startswith("_")
                },
            ]
        )

    @event("viewer.removed")
    async def push_viewer_removed(self, body):
        room = self._room_from_viewer_event(body)
        can_view_private = await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            room=room,
            permission=Permission.ROOM_VIEWERS,
        ) or await self.consumer.event.has_organizer_role_async(
            user=self.consumer.user,
            room=room,
        )
        if body.get("_visibility_changed") and can_view_private:
            return
        if not body.get("_show_publicly", True) and not can_view_private:
            return
        await self.consumer.send_json(
            [
                body["type"],
                {
                    k: v
                    for k, v in body.items()
                    if k != "type" and not k.startswith("_")
                },
            ]
        )

    @event("stream.change")
    async def push_stream_change(self, body):
        await self.consumer.send_json(
            [
                'room.stream.change',
                {
                    'stream': body.get('stream'),
                    'reload': body.get('reload', False)
                }
            ]
        )

    @event("stream.will_change")
    async def push_stream_will_change(self, body):
        await self.consumer.send_json(
            [
                'room.stream.will_change',
                {
                    'stream': body.get('stream'),
                    'starts_at': body.get('starts_at')
                }
            ]
        )

    @event("create", refresh_user=True)
    async def push_room_info(self, body):
        # Refresh event data from database to ensure we have the latest configuration
        await database_sync_to_async(self.consumer.event.refresh_from_db)()
        conf = await get_room_config_for_user(
            body["room"], self.consumer.event.id, self.consumer.user
        )
        if "room:view" not in conf["permissions"]:
            return
        await self.consumer.send_json(
            [
                body["type"],
                conf,
            ]
        )

    @command("config.list")
    @require_event_permission(Permission.ROOM_UPDATE)
    async def rooms_list(self, body):
        rooms = await database_sync_to_async(get_rooms)(self.consumer.event, user=None)
        await self.consumer.send_success(await database_sync_to_async(serialize_room_config)(rooms, many=True))

    @command("config.get")
    @room_action(permission_required=Permission.ROOM_UPDATE)
    async def config_get(self, body):
        await self.consumer.send_success(await database_sync_to_async(serialize_room_config)(self.room))

    @command("config.patch")
    @room_action(permission_required=Permission.ROOM_UPDATE)
    async def config_patch(self, body):
        newly_added_server_modules = newly_added_server_backed_room_modules(
            self.room.module_config,
            body.get("module_config"),
        )
        if "module_config" in body and newly_added_server_modules:
            if not await user_can_create_server_backed_room_during_development(
                self.consumer.user
            ):
                await self.consumer.send_error(code="config.denied")
                return
            if not await user_has_all_server_backed_room_create_permissions(
                self.consumer.event,
                self.consumer.user,
                newly_added_server_modules,
            ):
                await self.consumer.send_error(code="config.denied")
                return

        old = await database_sync_to_async(serialize_room_config)(self.room)
        validated_data, update_fields = await database_sync_to_async(
            validate_room_config_patch
        )(self.room, body)
        if validated_data is not None:
            for field in update_fields:
                setattr(self.room, field, validated_data[field])

            # Validate webhook URL via challenge verification when module_config changes
            if "module_config" in update_fields:
                try:
                    await self._verify_webhook_challenges(
                        old.get("module_config") or [],
                        self.room.module_config or [],
                    )
                except ConsumerException:
                    raise
                except Exception:
                    logger.exception("Webhook challenge verification failed")
                    await self.consumer.send_error(
                        code="webhook.verification_failed"
                    )
                    return

            # When module_config is updated, ensure open-viewer rooms have participant: [] so
            # implicit participant-role permissions (chat, questions, polls, BBB/join, etc.) work.
            # Only upgrade viewer: [] rooms missing participant; trait-restricted rooms unchanged.
            # Skip when the client sent trait_grants so explicit viewer-only configs stay put.
            if "module_config" in update_fields and "trait_grants" not in body:
                trait_grants = dict(self.room.trait_grants or {})
                viewer_is_open = trait_grants.get("viewer") == []
                if viewer_is_open and "participant" not in trait_grants:
                    trait_grants["participant"] = []
                    self.room.trait_grants = trait_grants
                    update_fields.add("trait_grants")

            new = await save_room(
                self.consumer.event,
                self.room,
                list(update_fields),
                old_data=old,
                by_user=self.consumer.user,
            )
            if "sorting_priority" in update_fields:
                await database_sync_to_async(normalize_after_priority_change)(
                    self.consumer.event,
                    self.room.id,
                    self.room.sorting_priority,
                )
                await database_sync_to_async(self.room.refresh_from_db)(
                    fields=["sorting_priority"]
                )
                new = await database_sync_to_async(serialize_room_config)(self.room)
            await self.consumer.send_success(new)
            await notify_event_change(self.consumer.event.id)
        else:
            await self.consumer.send_error(code="config.invalid")

    @command("config.reorder")
    @require_event_permission(Permission.ROOM_UPDATE)
    async def config_reorder(self, body):
        await reorder_rooms(self.consumer.event, body, self.consumer.user)
        rooms = await database_sync_to_async(get_rooms)(self.consumer.event, user=None)
        await self.consumer.send_success(await database_sync_to_async(serialize_room_config)(rooms, many=True))
        await notify_event_change(self.consumer.event.id)

    @command("delete")
    @room_action(permission_required=Permission.ROOM_DELETE)
    async def delete(self, body):
        await delete_room(self.consumer.event, self.room, by_user=self.consumer.user)
        await self.consumer.send_success()
        await get_channel_layer().group_send(
            f"event.{self.consumer.event.id}",
            {"type": "room.delete", "room": str(self.room.id)},
        )
        await notify_event_change(self.consumer.event.id)

    @event("delete")
    async def push_room_delete(self, body):
        await self.consumer.send_json([body["type"], {"id": body["room"]}])

    @command("schedule")
    @room_action(permission_required=Permission.ROOM_ANNOUNCE)
    async def change_schedule_data(self, body):
        old = await database_sync_to_async(serialize_room_config)(self.room)
        data = body.get("schedule_data")
        if data and not all(
            key in ["title", "session", "computeSession"] for key in data.keys()
        ):
            raise ConsumerException(
                code="room.unknown_schedule_data",
                message="Unknown schedule data",
            )

        await self.consumer.send_success({})
        self.room.schedule_data = data
        await save_room(
            self.consumer.event,
            self.room,
            ["schedule_data"],
            by_user=self.consumer.user,
            old_data=old,
        )
        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            {
                "type": "room.schedule",
                "schedule_data": data,
                "room": str(self.room.pk),
            },
        )

    @event("schedule")
    async def push_schedule_data(self, body):
        # Refresh event data from database to ensure we have the latest configuration
        await database_sync_to_async(self.consumer.event.refresh_from_db)()
        config = await get_room_config_for_user(
            body["room"], self.consumer.event.id, self.consumer.user
        )
        if "room:view" not in config["permissions"]:
            return
        await self.consumer.send_json(
            [
                body["type"],
                {
                    "room": config["id"],
                    "schedule_data": config.get("schedule_data"),
                },
            ]
        )

    @command("invite.anonymous.link")
    @room_action(
        permission_required=[
            Permission.ROOM_UPDATE,
            Permission.ROOM_INVITE_ANONYMOUS,
        ]
    )
    async def invite_anonymous_link(self, body):
        invite, created = await database_sync_to_async(
            AnonymousInvite.objects.get_or_create
        )(
            event=self.consumer.event,
            room=self.room,
            expires__gte=now() + timedelta(days=10),
            defaults=dict(
                expires=now() + timedelta(days=90),
            ),
        )
        await self.consumer.send_success(
            {"url": urljoin(settings.SHORT_URL, "/" + invite.short_token)}
        )
