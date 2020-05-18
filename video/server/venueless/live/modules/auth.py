import logging

from venueless.core.permissions import Permission
from venueless.core.services.chat import ChatService
from venueless.core.services.user import get_public_user, get_user, update_user
from venueless.core.services.world import get_world, get_world_config_for_user
from venueless.core.utils.jwt import decode_token
from venueless.live.channels import GROUP_USER, GROUP_WORLD
from venueless.live.decorators import require_world_permission

logger = logging.getLogger(__name__)


class AuthModule:
    async def login(self):
        if not self.content[1] or "token" not in self.content[1]:
            client_id = self.content[1].get("client_id")
            if not client_id:
                await self.consumer.send_error(code="auth.missing_id_or_token")
                return
            user = await get_user(
                self.world_id, with_client_id=client_id, serialize=False
            )
        else:
            token = await decode_token(self.content[1]["token"], self.world_id)
            if not token:
                await self.consumer.send_error(code="auth.invalid_token")
                return
            user = await get_user(self.world_id, with_token=token, serialize=False)

        if not user or not await self.world.has_permission_async(
            user=user, permission=Permission.WORLD_VIEW
        ):
            await self.consumer.send_json(["authentication.failed", {}])
            return

        self.consumer.user = user
        await self.consumer.send_json(
            [
                "authenticated",
                {
                    "user.config": self.consumer.user.serialize_public(),
                    "world.config": await get_world_config_for_user(user),
                    "chat.channels": await ChatService(
                        self.world_id
                    ).get_channels_for_user(self.consumer.user.id, is_volatile=False),
                },
            ]
        )
        await self.consumer.channel_layer.group_add(
            GROUP_USER.format(id=self.consumer.user.id), self.consumer.channel_name
        )
        await self.consumer.channel_layer.group_add(
            GROUP_WORLD.format(id=self.world_id), self.consumer.channel_name
        )

    async def reload_user(self):
        self.consumer.user = await get_user(
            self.world_id, with_id=self.consumer.user.id, serialize=False
        )

    @require_world_permission(Permission.WORLD_VIEW)
    async def update(self):
        user = await update_user(
            self.world_id,
            self.consumer.user.id,
            public_data=self.content[2],
            serialize=False,
        )
        self.consumer.user = user
        await self.consumer.send_success()
        await self.consumer.user_broadcast("user.updated", user.serialize_public())

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world_id = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.world = await get_world(self.world_id)
        if content[0] == "authenticate":
            await self.login()
        elif content[0] == "user.update":
            await self.update()
        elif content[0] == "user.fetch":
            await self.fetch(content[2].get("id"))
        else:
            await self.consumer.send_error(code="user.unknown_command")

    @require_world_permission(Permission.WORLD_VIEW)
    async def fetch(self, id):
        user = await get_public_user(self.world_id, id,)
        if user:
            await self.consumer.send_success(user)
        else:
            await self.consumer.send_error(code="user.not_found")

    async def dispatch_disconnect(self, consumer, close_code):
        self.consumer = consumer
        if self.consumer.user:
            await self.consumer.channel_layer.group_discard(
                GROUP_USER.format(id=self.consumer.user.id), self.consumer.channel_name,
            )
            await self.consumer.channel_layer.group_discard(
                GROUP_WORLD.format(id=self.world_id), self.consumer.channel_name
            )
