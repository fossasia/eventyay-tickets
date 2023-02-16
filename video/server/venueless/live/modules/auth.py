import logging
import time
from urllib.parse import urljoin

import jwt
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.conf import settings
from django.core.signing import dumps
from django.urls import reverse
from sentry_sdk import configure_scope

from venueless.core.permissions import Permission
from venueless.core.services.announcement import get_announcements
from venueless.core.services.chat import ChatService
from venueless.core.services.connections import (
    get_user_connection_count,
    register_user_connection,
    unregister_user_connection,
)
from venueless.core.services.user import (
    AuthError,
    block_user,
    delete_user,
    end_view,
    get_blocked_users,
    get_public_user,
    get_public_users,
    list_users,
    login,
    set_user_banned,
    set_user_free,
    set_user_silenced,
    unblock_user,
    update_user,
    user_broadcast,
)
from venueless.core.utils.redis import aioredis
from venueless.core.utils.statsd import statsd
from venueless.importers.tasks import conftool_update_schedule
from venueless.live.channels import GROUP_USER, GROUP_WORLD
from venueless.live.decorators import command, require_world_permission
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class AuthModule(BaseModule):
    prefix = "user"

    def __init__(self, consumer):
        super().__init__(consumer)
        self._current_view = None

    async def login(self, body):
        kwargs = {
            "world": self.consumer.world,
        }
        if not body or "token" not in body:
            client_id = body.get("client_id")
            if not client_id:
                async with statsd() as s:
                    s.increment(
                        f"authentication.failed,reason=missing_token,world={self.consumer.world.pk}"
                    )
                await self.consumer.send_error(code="auth.missing_id_or_token")
                return
            kwargs["client_id"] = client_id
        else:
            try:
                token = self.consumer.world.decode_token(
                    body["token"], allow_raise=True
                )
            except jwt.exceptions.ExpiredSignatureError:
                async with statsd() as s:
                    s.increment(
                        f"authentication.failed,reason=expired_token,world={self.consumer.world.pk}"
                    )
                    await self.consumer.send_error(code="auth.expired_token")
                    return
            except jwt.exceptions.InvalidTokenError:
                async with statsd() as s:
                    s.increment(
                        f"authentication.failed,reason=invalid_token,world={self.consumer.world.pk}"
                    )
                    await self.consumer.send_error(code="auth.invalid_token")
                    return
            kwargs["token"] = token

        try:
            login_result = await database_sync_to_async(login)(**kwargs)
        except AuthError as e:
            async with statsd() as s:
                s.increment(
                    f"authentication.failed,reason=denied,world={self.consumer.world.pk}"
                )
            await self.consumer.send_error(code=e.code)
            return

        self.consumer.user = login_result.user
        self._current_view = login_result.view
        if settings.SENTRY_DSN:
            with configure_scope() as scope:
                scope.user = {"id": str(self.consumer.user.id)}

        async with aioredis() as redis:
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
                        trait_badges_map=self.consumer.world.config.get(
                            "trait_badges_map"
                        ),
                        include_client_state=True,
                    ),
                    "world.config": login_result.world_config,
                    "chat.channels": login_result.chat_channels,
                    "chat.read_pointers": read_pointers,
                    "exhibition": login_result.exhibition_data,
                    "announcements": await get_announcements(
                        world=self.consumer.world.id, moderator=False
                    ),
                },
            ]
        )
        self.consumer.known_room_id_cache = {
            r["id"] for r in login_result.world_config["rooms"]
        }

        if not await self.consumer.world.has_permission_async(
            user=self.consumer.user, permission=Permission.WORLD_CONNECTIONS_UNLIMITED
        ):
            await self._enforce_connection_limit()

        await self.consumer.channel_layer.group_add(
            GROUP_USER.format(id=self.consumer.user.id), self.consumer.channel_name
        )
        await self.consumer.channel_layer.group_add(
            GROUP_WORLD.format(id=self.consumer.world.id), self.consumer.channel_name
        )

        await ChatService(self.consumer.world).enforce_forced_joins(self.consumer.user)

        async with statsd() as s:
            s.increment(f"authentication.completed,world={self.consumer.world.pk}")

        if self.consumer.world.config.get("pretalx", {}).get("conftool"):
            async with aioredis() as redis:
                # This is a very hacky replacement of a cronjob. The main advantage is that it will only run while
                # the world is in use and stop running after the event. Let's see how it works out in the real world.
                if await redis.set(
                    f"conftool:update.triggered:{self.consumer.world.pk}",
                    "yes",
                    expire=300,
                    exist=redis.SET_IF_NOT_EXIST,
                ):
                    await sync_to_async(conftool_update_schedule.apply_async)(
                        kwargs={"world": str(self.consumer.world.id)}
                    )

    async def _enforce_connection_limit(self):
        connection_limit = self.consumer.world.config.get("connection_limit")
        if not connection_limit:
            return

        message = {"type": "connection.replaced"}

        if settings.REDIS_USE_PUBSUB:
            async with aioredis() as redis:
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
                        group_send_lua, keys=channel_redis_keys, args=args
                    )

    @command("update")
    @require_world_permission(Permission.WORLD_VIEW)
    async def update(self, body):
        user = await database_sync_to_async(update_user)(
            self.consumer.world.id,
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
                trait_badges_map=self.consumer.world.config.get("trait_badges_map"),
                include_client_state=True,
            ),
            user.pk,
            self.consumer.socket_id,
        )
        await self.consumer.user.refresh_from_db_if_outdated(allowed_age=0)
        await ChatService(self.consumer.world).enforce_forced_joins(self.consumer.user)

    @command("admin.update")
    @require_world_permission(Permission.WORLD_USERS_MANAGE)
    async def admin_update(self, body):
        user = await database_sync_to_async(update_user)(
            self.consumer.world.id,
            body.pop("id"),
            data=body,
            is_admin=True,
            serialize=False,
        )
        await user_broadcast(
            "user.updated",
            user.serialize_public(
                trait_badges_map=self.consumer.world.config.get("trait_badges_map")
            ),
            user.pk,
            self.consumer.socket_id,
        )
        await self.consumer.send_success()

    @command("fetch")
    @require_world_permission(Permission.WORLD_VIEW)
    async def fetch(self, body):
        if "ids" in body:
            users = await get_public_users(
                self.consumer.world.id,
                ids=body.get("ids")[:100],
                include_admin_info=await self.consumer.world.has_permission_async(
                    user=self.consumer.user, permission=Permission.WORLD_USERS_MANAGE
                ),
                trait_badges_map=self.consumer.world.config.get("trait_badges_map"),
            )
            await self.consumer.send_success({u["id"]: u for u in users})
        elif "pretalx_ids" in body:
            users = await get_public_users(
                self.consumer.world.id,
                pretalx_ids=body.get("pretalx_ids")[:100],
                include_admin_info=await self.consumer.world.has_permission_async(
                    user=self.consumer.user, permission=Permission.WORLD_USERS_MANAGE
                ),
                trait_badges_map=self.consumer.world.config.get("trait_badges_map"),
            )
            await self.consumer.send_success({u["pretalx_id"]: u for u in users})
        else:
            user = await get_public_user(
                self.consumer.world.id,
                body.get("id"),
                include_admin_info=await self.consumer.world.has_permission_async(
                    user=self.consumer.user, permission=Permission.WORLD_USERS_MANAGE
                ),
                trait_badges_map=self.consumer.world.config.get("trait_badges_map"),
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
                GROUP_WORLD.format(id=self.consumer.world.id),
                self.consumer.channel_name,
            )
            await unregister_user_connection(
                self.consumer.user.id, self.consumer.channel_name
            )
        if self._current_view and self.consumer.world:
            await database_sync_to_async(end_view)(
                self._current_view,
                delete=not self.consumer.world.config.get("track_world_views", False),
            )

    @command("list")
    @require_world_permission(Permission.WORLD_USERS_LIST)
    async def list(self, body):
        users = await get_public_users(
            self.consumer.world.pk,
            include_admin_info=await self.consumer.world.has_permission_async(
                user=self.consumer.user, permission=Permission.WORLD_USERS_MANAGE
            ),
            include_banned=not body
            or body.get("include_banned", True)
            and await self.consumer.world.has_permission_async(
                user=self.consumer.user, permission=Permission.WORLD_USERS_MANAGE
            ),
            trait_badges_map=self.consumer.world.config.get("trait_badges_map"),
        )
        await self.consumer.send_success({"results": users})

    @command("list.search")
    async def user_list(self, body):
        list_conf = self.consumer.world.config.get("user_list", {})
        page_size = list_conf.get("page_size", 20)
        search_min_chars = list_conf.get("search_min_chars", 0)
        profile_fields = self.consumer.world.config.get("profile_fields", {})
        badge = body.get("badge")
        search_fields = [
            field["id"]
            for field in filter(lambda f: f.get("searchable", False), profile_fields)
            if "id" in field
        ]
        if len(body["search_term"]) < search_min_chars and not badge:
            result = {
                "results": [],
                "isLastPage": True,
            }
        else:
            result = await list_users(
                world_id=self.consumer.world.id,
                page=body["page"],
                page_size=page_size,
                search_term=body["search_term"],
                badge=badge,
                search_fields=search_fields,
                include_admin_info=await self.consumer.world.has_permission_async(
                    user=self.consumer.user, permission=Permission.WORLD_USERS_MANAGE
                ),
                include_banned=body.get("include_banned", True)
                and await self.consumer.world.has_permission_async(
                    user=self.consumer.user, permission=Permission.WORLD_USERS_MANAGE
                ),
                trait_badges_map=self.consumer.world.config.get("trait_badges_map"),
            )
        await self.consumer.send_success(result)

    @command("delete")
    @require_world_permission(Permission.WORLD_USERS_MANAGE)
    async def delete(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.delete.self")
            return
        ok = await delete_user(
            self.consumer.world, body.get("id"), by_user=self.consumer.user
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
    @require_world_permission(Permission.WORLD_USERS_MANAGE)
    async def ban(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.ban.self")
            return
        ok = await set_user_banned(
            self.consumer.world, body.get("id"), by_user=self.consumer.user
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
    @require_world_permission(Permission.WORLD_USERS_MANAGE)
    async def silence(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.silence.self")
            return
        ok = await set_user_silenced(
            self.consumer.world, body.get("id"), by_user=self.consumer.user
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
    @require_world_permission(Permission.WORLD_USERS_MANAGE)
    async def reactivate(self, body):
        if body.get("id") == str(self.consumer.user.id):
            await self.consumer.send_error(code="user.reactivate.self")
            return
        ok = await set_user_free(
            self.consumer.world,
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
            self.consumer.world,
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
            self.consumer.world,
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
            self.consumer.world,
        )
        await self.consumer.send_success({"users": users})

    @command("online_status")
    @require_world_permission(Permission.WORLD_VIEW)
    async def online_state(self, body):
        resp = {i: (await get_user_connection_count(i)) > 0 for i in body.get("ids")}
        await self.consumer.send_success(resp)

    @command("social.connect")
    @require_world_permission(Permission.WORLD_VIEW)
    async def social_connect(self, body):
        network = body.get("network")

        if not body.get("return_url"):
            await self.consumer.send_error(code="user.social.return_url_required")
            return

        if network not in ("twitter", "linkedin"):
            await self.consumer.send_error(code="user.social.unknown")
            return

        payload = {
            "network": network,
            "return_url": body.get("return_url"),
            "world": self.consumer.world.pk,
            "user": str(self.consumer.user.pk),
        }
        token = dumps(payload, salt="venueless.social.start", compress=True)

        await self.consumer.send_success(
            {
                "url": urljoin(settings.SITE_URL, reverse(f"social:{network}.start"))
                + "?token="
                + token,
            }
        )
