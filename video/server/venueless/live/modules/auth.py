import logging
import time

from channels.db import database_sync_to_async
from django.conf import settings
from sentry_sdk import configure_scope

from venueless.core.permissions import Permission
from venueless.core.services.user import (
    get_public_user,
    get_public_users,
    login,
    update_user,
    get_user, set_user_banned, set_user_free, set_user_silenced)
from venueless.live.channels import GROUP_USER, GROUP_WORLD
from venueless.live.decorators import command, require_world_permission
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class AuthModule(BaseModule):
    prefix = "user"

    async def login(self, body):
        kwargs = {
            "world": self.consumer.world,
        }
        if not body or "token" not in body:
            client_id = body.get("client_id")
            if not client_id:
                await self.consumer.send_error(code="auth.missing_id_or_token")
                return
            kwargs["client_id"] = client_id
        else:
            token = self.consumer.world.decode_token(body["token"])
            if not token:
                await self.consumer.send_error(code="auth.invalid_token")
                return
            kwargs["token"] = token

        login_result = await login(**kwargs)
        if not login_result:
            await self.consumer.send_error(code="auth.denied")
            return

        self.consumer.user = login_result.user
        if settings.SENTRY_DSN:
            with configure_scope() as scope:
                scope.user = {"id": str(self.consumer.user.id)}

        await self.consumer.send_json(
            [
                "authenticated",
                {
                    "user.config": self.consumer.user.serialize_public(),
                    "world.config": login_result.world_config,
                    "chat.channels": login_result.chat_channels,
                },
            ]
        )

        await self._enforce_connection_limit()

        await self.consumer.channel_layer.group_add(
            GROUP_USER.format(id=self.consumer.user.id), self.consumer.channel_name
        )
        await self.consumer.channel_layer.group_add(
            GROUP_WORLD.format(id=self.consumer.world.id), self.consumer.channel_name
        )

    async def _enforce_connection_limit(self):
        connection_limit = self.consumer.world.config.get("connection_limit")
        if not connection_limit:
            return

        message = {"type": "connection.replaced"}

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

        logger.debug(f"limit {connection_limit} len {len(channel_names)}")
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

        for connection_index, channel_redis_keys in connection_to_channel_keys.items():
            group_send_lua = (
                """ for i=1,#KEYS do
                            redis.call('LPUSH', KEYS[i], ARGV[i])
                            redis.call('EXPIRE', KEYS[i], %d)
                        end
                        """
                % cl.expiry
            )

            args = [
                channel_keys_to_message[channel_key]
                for channel_key in channel_redis_keys
            ]
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
            public_data=body,
            serialize=False,
        )
        self.consumer.user = user
        await self.consumer.send_success()
        await self.consumer.user_broadcast("user.updated", user.serialize_public())

    @command("fetch")
    @require_world_permission(Permission.WORLD_VIEW)
    async def fetch(self, body):
        if "ids" in body:
            users = await get_public_users(
                self.consumer.world.id, ids=body.get("ids")[:100]
            )
            await self.consumer.send_success({u["id"]: u for u in users})
        else:
            user = await get_public_user(self.consumer.world.id, body.get("id"),)
            if user:
                await self.consumer.send_success(user)
            else:
                await self.consumer.send_error(code="user.not_found")

    async def dispatch_disconnect(self, close_code):
        if self.consumer.user:
            await self.consumer.channel_layer.group_discard(
                GROUP_USER.format(id=self.consumer.user.id), self.consumer.channel_name,
            )
            await self.consumer.channel_layer.group_discard(
                GROUP_WORLD.format(id=self.consumer.world.id),
                self.consumer.channel_name,
            )

    @command("list")
    @require_world_permission(Permission.WORLD_USERS_LIST)
    async def list(self, body):
        users = await get_public_users(
            self.consumer.world.pk,
        )
        await self.consumer.send_success({"results": users})

    @command("ban")
    @require_world_permission(Permission.WORLD_USERS_MANAGE)
    async def ban(self, body):
        ok = await set_user_banned(self.consumer.world.id, body.get("id"),)
        if ok:
            await self.consumer.send_success({})
            # Force user browser to reload instead of drop to kick out of e.g. BBB sessions
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(body.get('id')),
                {"type": "connection.reload"},
            )
        else:
            await self.consumer.send_error(code="user.not_found")

    @command("silence")
    @require_world_permission(Permission.WORLD_USERS_MANAGE)
    async def silence(self, body):
        ok = await set_user_silenced(self.consumer.world.id, body.get("id"),)
        if ok:
            await self.consumer.send_success({})
            # Force user browser to reload instead of drop to kick out of e.g. BBB sessions
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(body.get('id')),
                {"type": "connection.reload"},
            )
        else:
            await self.consumer.send_error(code="user.not_found")

    @command("reactivate")
    @require_world_permission(Permission.WORLD_USERS_MANAGE)
    async def reactivate(self, body):
        ok = await set_user_free(self.consumer.world.id, body.get("id"),)
        if ok:
            await self.consumer.send_success({})
        else:
            await self.consumer.send_error(code="user.not_found")
