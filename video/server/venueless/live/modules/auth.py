import logging

from venueless.core.services.chat import ChatService
from venueless.core.services.user import get_public_user, get_user, update_user
from venueless.core.services.world import get_world_config_for_user
from venueless.core.utils.jwt import decode_token
from venueless.live.channels import GROUP_USER, GROUP_WORLD

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
        self.consumer.user = user.serialize_public()
        await self.consumer.send_json(
            [
                "authenticated",
                {
                    "user.config": self.consumer.user,
                    "world.config": await get_world_config_for_user(user),
                    "chat.channels": await ChatService(
                        self.world
                    ).get_channels_for_user(
                        self.consumer.user["id"], is_volatile=False
                    ),
                },
            ]
        )
        await self.consumer.channel_layer.group_add(
            GROUP_USER.format(id=self.consumer.user["id"]), self.consumer.channel_name
        )
        await self.consumer.channel_layer.group_add(
            GROUP_WORLD.format(id=self.world), self.consumer.channel_name
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

    async def push_world_update(self):
        world_config = await get_world_config_for_user(
            await get_user(
                self.world, with_id=self.consumer.user["id"], serialize=False
            )
        )
        await self.consumer.send_json(["world.updated", world_config])

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

    async def dispatch_event(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.service = ChatService(self.world)
        if self.content["type"] == "world.update":
            await self.push_world_update()
        else:  # pragma: no cover
            logger.warning(
                f'Ignored unknown event {content["type"]}'
            )  # ignore unknown event

    async def dispatch_disconnect(self, consumer, close_code):
        self.consumer = consumer
        if self.consumer.user:
            await self.consumer.channel_layer.group_discard(
                GROUP_USER.format(id=self.consumer.user["id"]),
                self.consumer.channel_name,
            )
            await self.consumer.channel_layer.group_discard(
                GROUP_WORLD.format(id=self.world), self.consumer.channel_name
            )
