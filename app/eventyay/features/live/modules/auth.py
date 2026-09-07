import datetime
import logging
import time
import uuid
from urllib.parse import urljoin

import jwt
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.conf import settings
from django.core.signing import dumps
from django.urls import reverse
from sentry_sdk import configure_scope

from eventyay.base.models import User
from eventyay.base.models.auth import ShortToken
from eventyay.core.permissions import Permission
from eventyay.base.services.announcement import get_announcements
from eventyay.features.live.modules.announcement import is_announcements_enabled
from eventyay.base.services.chat import ChatService
from eventyay.base.services.connections import (
    get_user_connection_count,
    register_user_connection,
    unregister_user_connection,
)
from eventyay.base.services.user import (
    AuthError,
    block_user,
    delete_user,
    end_view,
    get_blocked_users,
    get_public_user,
    get_public_users,
    get_user_by_id,
    list_users,
    login,
    set_user_banned,
    set_user_free,
    set_user_silenced,
    unblock_user,
    update_user,
    user_broadcast,
)
from eventyay.core.utils.redis import aredis
from eventyay.core.utils.statsd import statsd
from eventyay.features.importers.tasks import conftool_update_schedule
from eventyay.features.live.channels import GROUP_USER, GROUP_EVENT
from eventyay.features.live.decorators import command, require_event_permission
from eventyay.features.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class AuthModule(BaseModule):
    prefix = "user"

    def __init__(self, consumer):
        super().__init__(consumer)
        self._current_view = None

    def _event_config(self):
        """Return event config dict (never None)."""
        return (getattr(self.consumer.event, "config", None) or {}) if self.consumer.event else {}

    async def _include_admin_user_info(self):
        """Admin user list/detail fields match EVENT_USERS_LIST UI, not only manage."""
        return await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=Permission.EVENT_USERS_LIST,
        )

    async def login(self, body):
        kwargs = {
            "event": self.consumer.event,
        }
        body = body or {}
        if "token" not in body or not body.get("token"):
            session_user = self.consumer.scope.get("user")
            session = self.consumer.scope.get("session")
            session_key = getattr(session, "session_key", None)
            is_authorized_session_user = False
            if session_user and getattr(session_user, "is_authenticated", False):
                from eventyay.eventyay_common.video.traits_sync import is_platform_event_admin
                is_admin = await database_sync_to_async(is_platform_event_admin)(session_user, session_key=session_key)
                has_perm = await database_sync_to_async(
                    lambda: session_user.has_event_permission(
                        self.consumer.event.organizer, self.consumer.event
                    ) or session_user.has_organizer_permission(
                        self.consumer.event.organizer
                    )
                )()
                is_authorized_session_user = bool(is_admin or has_perm)

            if is_authorized_session_user:
                kwargs["platform_user"] = session_user
                kwargs["session_key"] = session_key
            else:
                client_id = body.get("client_id")
                if not client_id:
                    async with statsd() as s:
                        s.increment(
                            f"authentication.failed,reason=missing_token,event={self.consumer.event.pk}"
                        )
                    await self.consumer.send_error(code="auth.missing_id_or_token")
                    return
                kwargs["client_id"] = client_id
                if "invite_token" in body:
                    kwargs["invite_token"] = body.get("invite_token")
        else:
            try:
                # decode_token may read event.settings (DB-backed) when JWT_secrets are unset
                token = await database_sync_to_async(
                    self.consumer.event.decode_token
                )(body["token"], allow_raise=True)
            except jwt.exceptions.ExpiredSignatureError:
                async with statsd() as s:
                    s.increment(
                        f"authentication.failed,reason=expired_token,event={self.consumer.event.pk}"
                    )
                    await self.consumer.send_error(code="auth.expired_token")
                    return
            except jwt.exceptions.InvalidTokenError:
                async with statsd() as s:
                    s.increment(
                        f"authentication.failed,reason=invalid_token,event={self.consumer.event.pk}"
                    )
                    await self.consumer.send_error(code="auth.invalid_token")
                    return
            kwargs["token"] = token

        try:
            login_result = await database_sync_to_async(login)(**kwargs)
        except AuthError as e:
            async with statsd() as s:
                s.increment(
                    f"authentication.failed,reason=denied,event={self.consumer.event.pk}"
                )
            await self.consumer.send_error(code=e.code)
            return

        self.consumer.user = login_result.user
        self._current_view = login_result.view
        if settings.SENTRY_DSN:
            with configure_scope() as scope:
                scope.user = {"id": str(self.consumer.user.id)}

        async with aredis() as redis:
            redis_read = await redis.hgetall(f"chat:read:{self.consumer.user.id}")
            read_pointers = {k.decode(): int(v.decode()) for k, v in redis_read.items()}

        await register_user_connection(
            self.consumer.user.id, self.consumer.channel_name
        )
        await self.consumer.send_json(
            [
                "authenticated",
                {
                    "user.config": self.consumer.user.serialize_public(
                        trait_badges_map=self._event_config().get(
                            "trait_badges_map"
                        ),
                        include_client_state=True,
                        include_personal_data=True,
                    ),
                    "event.config": login_result.event_config,
                    "chat.channels": login_result.chat_channels,
                    "chat.read_pointers": read_pointers,
                    "chat.notification_counts": login_result.chat_notification_counts,
                    "announcements": (
                        await get_announcements(
                            event=self.consumer.event.id, moderator=False
                        )
                        if is_announcements_enabled(self.consumer.event)
                        else []
                    ),
                },
            ]
        )
        self.consumer.known_room_id_cache = {
            r["id"] for r in login_result.event_config["rooms"]
        }

        if not await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=Permission.EVENT_CONNECTIONS_UNLIMITED,
        ):
            await self._enforce_connection_limit()

        await self.consumer.channel_layer.group_add(
            GROUP_USER.format(id=self.consumer.user.id),
            self.consumer.channel_name,
        )
        await self.consumer.channel_layer.group_add(
            GROUP_EVENT.format(id=self.consumer.event.id),
            self.consumer.channel_name,
        )

        await ChatService(self.consumer.event).enforce_forced_joins(self.consumer.user)

        async with statsd() as s:
            s.increment(f"authentication.completed,event={self.consumer.event.pk}")

        if self._event_config().get("pretalx", {}).get("conftool"):
            async with aredis() as redis:
                # This is a very hacky replacement of a cronjob. The main advantage is that it will only run while
                # the event is in use and stop running after the event. Let's see how it works out in the real event.
                if await redis.set(
                    f"conftool:update.triggered:{self.consumer.event.pk}",
                    "yes",
                    ex=300,
                    nx=True,
                ):
                    await sync_to_async(conftool_update_schedule.apply_async)(
                        kwargs={"event": str(self.consumer.event.id)}
                    )

    async def _enforce_connection_limit(self):
        connection_limit = self._event_config().get("connection_limit")
        if not connection_limit:
            return

        message = {"type": "connection.replaced"}

        if settings.REDIS_USE_PUBSUB:
            async with aredis() as redis:
                channels_to_drop = await redis.lrange(
                    f"connections.list.user:{self.consumer.user.id}",
                    0,
                    -1 * connection_limit - 1,
                )
                for c in channels_to_drop:
                    await self.consumer.channel_layer.send(c.decode(), message)
        else:
            channel_names = []
            group = GROUP_USER.format(id=self.consumer.user.id)
            cl = self.consumer.channel_layer
            key = cl._group_key(group)
            async with cl.connection(cl.consistent_hash(group)) as connection:
                # Discard old channels based on group_expiry
                await connection.zremrangebyscore(
                    key, min=0, max=int(time.time()) - cl.group_expiry
                )
                channel_names += [
                    x.decode("utf8") for x in await connection.zrange(key, 0, -1)
                ]

            if len(channel_names) < connection_limit:
                return

            if connection_limit == 1:
                channels_to_drop = channel_names
            else:
                channels_to_drop = channel_names[: -1 * (connection_limit - 1)]

            (
                connection_to_channel_keys,
                channel_keys_to_message,
                channel_keys_to_capacity,
            ) = cl._map_channel_keys_to_connection(channels_to_drop, message)

            for (
                connection_index,
                channel_redis_keys,
            ) in connection_to_channel_keys.items():
                group_send_lua = """
                    local current_time = ARGV[#ARGV - 1]
                    local expiry = ARGV[#ARGV]
                    for i=1,#KEYS do
                        redis.call('ZADD', KEYS[i], current_time, ARGV[i])
                        redis.call('EXPIRE', KEYS[i], expiry)
                    end
                    """

                args = [
                    channel_keys_to_message[channel_key]
                    for channel_key in channel_redis_keys
                ]
                args += [int(time.time()), cl.expiry]
                async with cl.connection(connection_index) as connection:
                    await connection.eval(
                        group_send_lua,
                        len(channel_redis_keys),
                        *channel_redis_keys,
                        *args,
                    )

    @command("update")
    @require_event_permission(Permission.EVENT_VIEW)
    async def update(self, body):
        user = await database_sync_to_async(update_user)(
            self.consumer.event.id,
            self.consumer.user.id,
            data=body,
            is_admin=False,
            serialize=False,
        )
        self.consumer.user = user
        await self.consumer.send_success()
        await user_broadcast(
            "user.updated",
            user.serialize_public(
                trait_badges_map=self._event_config().get("trait_badges_map"),
                include_client_state=True,
            ),
            user.pk,
            self.consumer.socket_id,
        )
        await self.consumer.user.refresh_from_db_if_outdated(allowed_age=0)
        await ChatService(self.consumer.event).enforce_forced_joins(self.consumer.user)

    @command("set_publicly_visible")
    @require_event_permission(Permission.EVENT_VIEW)
    async def set_publicly_visible(self, body):
        """Toggle the user's show_publicly flag from within the video platform."""
        body = body or {}
        show_publicly = body.get("show_publicly")
        if not isinstance(show_publicly, bool):
            await self.consumer.send_error(code="user.set_publicly_visible.invalid")
            return

        old_show_publicly = bool(self.consumer.user.show_publicly)

        def _save_and_get_active_room_ids(user, value):
            from eventyay.base.models.room import RoomView

            user.show_publicly = value
            user.save(update_fields=["show_publicly"])
            return list(
                RoomView.objects.filter(user=user, end__isnull=True)
                .values_list("room_id", flat=True)
                .distinct()
            )

        active_room_ids = await database_sync_to_async(_save_and_get_active_room_ids)(
            self.consumer.user, show_publicly
        )

        if old_show_publicly != show_publicly and active_room_ids:
            from eventyay.features.live.channels import GROUP_ROOM_VIEWERS

            for room_id in active_room_ids:
                if show_publicly:
                    await self.consumer.channel_layer.group_send(
                        GROUP_ROOM_VIEWERS.format(id=room_id),
                        {
                            "type": "room.viewer.added",
                            "user": self.consumer.user.serialize_public(
                                trait_badges_map=self._event_config().get(
                                    "trait_badges_map"
                                )
                            ),
                            "_show_publicly": True,
                            "_room": str(room_id),
                        },
                    )
                else:
                    await self.consumer.channel_layer.group_send(
                        GROUP_ROOM_VIEWERS.format(id=room_id),
                        {
                            "type": "room.viewer.removed",
                            "user_id": str(self.consumer.user.id),
                            "_show_publicly": False,
                            "_visibility_changed": True,
                            "_room": str(room_id),
                        },
                    )

        await self.consumer.send_success({"show_publicly": show_publicly})

    @command("admin.update")
    @require_event_permission(Permission.EVENT_USERS_MANAGE)
    async def admin_update(self, body):
        user = await database_sync_to_async(update_user)(
            self.consumer.event.id,
            body.pop("id"),
            data=body,
            is_admin=True,
            serialize=False,
        )
        await user_broadcast(
            "user.updated",
            user.serialize_public(
                trait_badges_map=self._event_config().get("trait_badges_map"),
                include_client_state=user.type == User.UserType.KIOSK,
            ),
            user.pk,
            self.consumer.socket_id,
        )
        await self.consumer.send_success()

    @command("fetch")
    @require_event_permission(Permission.EVENT_VIEW)
    async def fetch(self, body):
        admin = await self._include_admin_user_info()
        if "ids" in body:
            users = await get_public_users(
                self.consumer.event.id,
                ids=body.get("ids")[:100],
                include_admin_info=admin,
                trait_badges_map=self._event_config().get("trait_badges_map"),
            )
            await self.consumer.send_success({u["id"]: u for u in users})
        elif "pretalx_ids" in body:
            users = await get_public_users(
                self.consumer.event.id,
                pretalx_ids=body.get("pretalx_ids")[:100],
                include_admin_info=admin,
                trait_badges_map=self._event_config().get("trait_badges_map"),
            )
            await self.consumer.send_success({u["pretalx_id"]: u for u in users})
        else:
            user = await get_public_user(
                self.consumer.event.id,
                body.get("id"),
                include_admin_info=admin,
                trait_badges_map=self._event_config().get("trait_badges_map"),
            )
            if user:
                await self.consumer.send_success(user)
            else:
                await self.consumer.send_error(code="user.not_found")

    async def dispatch_disconnect(self, close_code):
        if self.consumer.user:
            await self.consumer.channel_layer.group_discard(
                GROUP_USER.format(id=self.consumer.user.id),
                self.consumer.channel_name,
            )
            await self.consumer.channel_layer.group_discard(
                GROUP_EVENT.format(id=self.consumer.event.id),
                self.consumer.channel_name,
            )
            await unregister_user_connection(
                self.consumer.user.id, self.consumer.channel_name
            )
        if self._current_view and self.consumer.event:
            await database_sync_to_async(end_view)(
                self._current_view,
                delete=not self._event_config().get("track_event_views", True),
            )

    @command("list")
    @require_event_permission(Permission.EVENT_USERS_LIST)
    async def list(self, body):
        body = body or {}
        users = await get_public_users(
            self.consumer.event.pk,
            include_admin_info=await self._include_admin_user_info(),
            type=body.get("type", User.UserType.PERSON),
            include_banned=not body
            or body.get("include_banned", True)
            and await self.consumer.event.has_permission_async(
                user=self.consumer.user,
                permission=Permission.EVENT_USERS_MANAGE,
            ),
            trait_badges_map=self._event_config().get("trait_badges_map"),
        )
        await self.consumer.send_success({"results": users})

    @command("list.search")
    async def user_list(self, body):
        list_conf = self._event_config().get("user_list", {})
        page_size = list_conf.get("page_size", 20)
        search_min_chars = list_conf.get("search_min_chars", 0)
        badge = body.get("badge")
        search_fields = []
        if len(body["search_term"]) < search_min_chars and not badge:
            result = {
                "results": [],
                "isLastPage": True,
            }
        else:
            result = await list_users(
                event_id=self.consumer.event.id,
                page=body["page"],
                page_size=page_size,
                search_term=body["search_term"],
                badge=badge,
                search_fields=search_fields,
                include_admin_info=await self._include_admin_user_info(),
                include_banned=body.get("include_banned", True)
                and await self.consumer.event.has_permission_async(
                    user=self.consumer.user,
                    permission=Permission.EVENT_USERS_MANAGE,
                ),
                trait_badges_map=self._event_config().get("trait_badges_map"),
                include_private=await self.consumer.event.has_organizer_role_async(
                    user=self.consumer.user,
                ),
            )
        await self.consumer.send_success(result)

    @command("delete")
    @require_event_permission(Permission.EVENT_USERS_MANAGE)
    async def delete(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.delete.self")
            return
        ok = await delete_user(
            self.consumer.event, body.get("id"), by_user=self.consumer.user
        )
        if ok:
            await self.consumer.send_success({})
            # Force user browser to reload instead of drop to kick out of e.g. BBB sessions
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(id=body.get("id")),
                {"type": "connection.reload"},
            )
        else:
            await self.consumer.send_error(code="user.not_found")

    @command("ban")
    @require_event_permission(Permission.EVENT_USERS_MANAGE)
    async def ban(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.ban.self")
            return
        ok = await set_user_banned(
            self.consumer.event, body.get("id"), by_user=self.consumer.user
        )
        if ok:
            await self.consumer.send_success({})
            # Force user browser to reload instead of drop to kick out of e.g. BBB sessions
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(id=body.get("id")),
                {"type": "connection.reload"},
            )
        else:
            await self.consumer.send_error(code="user.not_found")

    @command("silence")
    @require_event_permission(Permission.EVENT_USERS_MANAGE)
    async def silence(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.silence.self")
            return
        ok = await set_user_silenced(
            self.consumer.event, body.get("id"), by_user=self.consumer.user
        )
        if ok:
            await self.consumer.send_success({})
            # Force user browser to reload instead of drop to kick out of e.g. BBB sessions
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(id=body.get("id")),
                {"type": "connection.reload"},
            )
        else:
            await self.consumer.send_error(code="user.not_found")

    @command("reactivate")
    @require_event_permission(Permission.EVENT_USERS_MANAGE)
    async def reactivate(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.reactivate.self")
            return
        ok = await set_user_free(
            self.consumer.event,
            body.get("id"),
            by_user=self.consumer.user,
        )
        if ok:
            await self.consumer.send_success({})
        else:
            await self.consumer.send_error(code="user.not_found")

    @command("block")
    async def block(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.block.self")
            return
        ok = await block_user(
            self.consumer.event,
            self.consumer.user,
            body.get("id"),
        )
        if ok:
            await self.consumer.send_success({})
        else:
            await self.consumer.send_error(code="user.not_found")

    @command("unblock")
    async def unblock(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.unblock.self")
            return
        ok = await unblock_user(
            self.consumer.event,
            self.consumer.user,
            body.get("id"),
        )
        if ok:
            await self.consumer.send_success({})
        else:
            await self.consumer.send_error(code="user.not_found")

    @command("list.blocked")
    async def list_blocked(self, body):
        users = await get_blocked_users(
            self.consumer.user,
            self.consumer.event,
        )
        await self.consumer.send_success({"users": users})

    @command("online_status")
    @require_event_permission(Permission.EVENT_VIEW)
    async def online_state(self, body):
        resp = {i: (await get_user_connection_count(i)) > 0 for i in body.get("ids")}
        await self.consumer.send_success(resp)

    @command("kiosk.create")
    @require_event_permission(Permission.EVENT_KIOSKS_MANAGE)
    async def kiosk_create(self, body):
        uid = str(uuid.uuid4())

        @database_sync_to_async
        def create_user():
            user = User.objects.create(
                type=User.UserType.KIOSK,
                token_id=uid,
                event=self.consumer.event,
                show_publicly=False,
                profile=(
                    body["profile"] if isinstance(body.get("profile"), dict) else {}
                ),
                traits=[],
            )
            user.event_grants.create(event=self.consumer.event, role="__kiosk")
            return user

        user = await create_user()

        await self.consumer.send_success({"user": str(user.pk)})

    @command("kiosk.fetch")
    @require_event_permission(Permission.EVENT_KIOSKS_MANAGE)
    async def kiosk_fetch(self, body):
        @database_sync_to_async
        def get_user(uid):
            user = get_user_by_id(self.consumer.event.pk, uid)
            if not user or user.type != User.UserType.KIOSK:
                return None
            user = user.serialize_public(
                include_admin_info=True,
                trait_badges_map=None,
                include_client_state=True,
            )
            cfg = self._event_config()
            jwt_secrets = cfg.get("JWT_secrets") or []
            if not jwt_secrets:
                # Fail gracefully if JWT secrets are not configured
                user["token"] = None
                return user
            jwt_config = jwt_secrets[0]
            iat = datetime.datetime.now(datetime.timezone.utc)
            exp = iat + datetime.timedelta(days=365)
            payload = {
                "iss": jwt_config.get("issuer", ""),
                "aud": jwt_config.get("audience", ""),
                "exp": exp,
                "iat": iat,
                "uid": user["token_id"],
                "traits": ["-kiosk"],
            }

            token = jwt.encode(payload, jwt_config.get("secret", ""), algorithm="HS256")
            st = ShortToken(event=self.consumer.event, long_token=token, expires=exp)
            st.save()
            user["token"] = st.short_token
            return user

        user = await get_user(body.get("id"))
        if user:
            await self.consumer.send_success(user)
        else:
            await self.consumer.send_error(code="user.not_found")

    @command("kiosk.update")
    @require_event_permission(Permission.EVENT_KIOSKS_MANAGE)
    async def kiosk_update(self, body):
        """Update a kiosk user profile (slides, room, display name, etc.)."""
        kiosk_id = body.get("id")
        profile = body.get("profile")
        if not kiosk_id or not isinstance(profile, dict):
            await self.consumer.send_error(code="auth.invalid_input")
            return

        @database_sync_to_async
        def load_kiosk(uid):
            user = get_user_by_id(self.consumer.event.pk, uid)
            if not user or user.type != User.UserType.KIOSK:
                return None
            return user

        kiosk_user = await load_kiosk(kiosk_id)
        if not kiosk_user:
            await self.consumer.send_error(code="user.not_found")
            return

        user = await database_sync_to_async(update_user)(
            self.consumer.event.id,
            kiosk_id,
            data={"profile": profile},
            is_admin=True,
            serialize=False,
        )
        await user_broadcast(
            "user.updated",
            user.serialize_public(
                trait_badges_map=self._event_config().get("trait_badges_map"),
                include_client_state=True,
            ),
            user.pk,
            self.consumer.socket_id,
        )
        await self.consumer.send_success()
