import logging

from channels.db import database_sync_to_async

from venueless.core.permissions import Permission
from venueless.core.services.user import get_public_user, login, update_user
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
            await self.consumer.send_json(["authentication.failed", {}])
            return

        self.consumer.user = login_result.user
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
        await self.consumer.channel_layer.group_add(
            GROUP_USER.format(id=self.consumer.user.id), self.consumer.channel_name
        )
        await self.consumer.channel_layer.group_add(
            GROUP_WORLD.format(id=self.consumer.world.id), self.consumer.channel_name
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
