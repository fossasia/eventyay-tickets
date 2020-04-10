from ...core.services.user import get_user, update_user
from channels.db import database_sync_to_async
from ...core.services.event import get_event_config


class AuthModule:
    async def login(self):
        if not self.content[1]:
            user = {"id": None}
        else:
            token = self.content[1]["token"]
            user = await get_user(token)
        self.consumer.scope["session"]["user_id"] = user["id"]
        self.consumer.scope["user"] = user
        await database_sync_to_async(self.consumer.scope["session"].save)()
        await self.consumer.send_json(
            [
                "authenticated",
                {
                    "user.config": user,
                    "event.config": await get_event_config(self.event),
                },
            ]
        )

    async def update(self):
        if not "user_id" in self.consumer.scope["session"]:
            raise
        await update_user(self.consumer.scope["session"]["user_id"], self.content[2])
        await self.consumer.send_json(["success", self.content[1], {}])

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.event = self.consumer.scope["url_route"]["kwargs"]["event"]
        if content[0] == "authenticate":
            await self.login()
        elif content[0] == "user.update":
            await self.update()
