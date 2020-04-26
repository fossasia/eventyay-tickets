import logging

from channels.db import database_sync_to_async

from stayseated.core.serializers.auth import PublicUserSerializer
from stayseated.core.services.chat import ChatService
from stayseated.core.services.user import get_public_user, get_user, update_user
from stayseated.core.services.world import get_world_config_for_user
from stayseated.core.utils.jwt import decode_token

logger = logging.getLogger(__name__)


class AuthModule:
    async def login(self):
        if not self.content[1] or "token" not in self.content[1]:
            client_id = self.content[1].get("client_id")
            if not client_id:
                await self.consumer.send_error(code="auth.missing_id_or_token")
                return
            user = await get_user(self.world, with_client_id=client_id, serialize=False)
        else:
            token = await decode_token(self.content[1]["token"], self.world)
            if not token:
                await self.consumer.send_error(code="auth.invalid_token")
                return
            user = await get_user(self.world, with_token=token, serialize=False)
        self.consumer.user = PublicUserSerializer().to_representation(user)
        await database_sync_to_async(self.consumer.scope["session"].save)()
        await self.consumer.send_json(
            [
                "authenticated",
                {
                    "user.config": self.consumer.user,
                    "world.config": await get_world_config_for_user(self.world, user),
                    "chat.channels": await ChatService(
                        self.world
                    ).get_channels_for_user(
                        self.consumer.user["id"], is_volatile=False
                    ),
                },
            ]
        )
        await self.consumer.channel_layer.group_add(
            f"user.{self.consumer.user['id']}", self.consumer.channel_name
        )

    async def update(self):
        new_data = await update_user(
            self.world, self.consumer.user["id"], public_data=self.content[2]
        )
        self.consumer.user = new_data
        await self.consumer.send_success()
        await self.consumer.user_broadcast(
            "user.updated", await get_public_user(self.world, self.consumer.user["id"])
        )

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world = self.consumer.scope["url_route"]["kwargs"]["world"]
        if content[0] == "authenticate":
            await self.login()
        elif content[0] == "user.update":
            await self.update()
        elif content[0] == "user.fetch":
            await self.fetch(content[2].get("id"))
        else:
            await self.consumer.send_error(code="user.unknown_command")

    async def fetch(self, id):
        user = await get_public_user(self.world, id,)
        if user:
            await self.consumer.send_success(user)
        else:
            await self.consumer.send_error(code="user.not_found")

    async def dispatch_disconnect(self, consumer, close_code):
        self.consumer = consumer
        if self.consumer.user:
            await self.consumer.channel_layer.group_discard(
                f"user.{self.consumer.user['id']}", self.consumer.channel_name
            )
