from channels.db import database_sync_to_async

from stayseated.core.services.event import get_event_config_for_user
from stayseated.core.services.user import get_user, update_user


class AuthModule:
    async def login(self):
        if not self.content[1] or not "token" in self.content[1]:
            client_id = self.content[1].get("client_id")
            if not client_id:
                await self.consumer.send_error(code="auth.missing_id_or_token")
                return
            user = await get_user(client_id=client_id)
        else:
            token = self.content[1]["token"]
            if not token:
                await self.consumer.send_error(code="auth.invalid_token")
                return
            user = await get_user(token=token)
        self.consumer.scope["session"]["user"] = user
        self.consumer.scope["user"] = user
        await database_sync_to_async(self.consumer.scope["session"].save)()
        await self.consumer.send_json(
            [
                "authenticated",
                {
                    "user.config": user,
                    "event.config": await get_event_config_for_user(self.event, user),
                },
            ]
        )

    async def update(self):
        if not "user_id" in self.consumer.scope["session"]:
            raise
        await update_user(self.consumer.scope["session"]["user"], self.content[2])
        await self.consumer.send_json(["success", self.content[1], {}])

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.event = self.consumer.scope["url_route"]["kwargs"]["event"]
        if content[0] == "authenticate":
            await self.login()
        elif content[0] == "user.update":
            await self.update()
