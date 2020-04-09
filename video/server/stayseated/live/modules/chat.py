from ...core.services.event import get_room_config
from ...core.utils.redis import aioredis


class ChatModule:
    async def join(self):
        room_id = self.content[2]["room"]
        room_config = await get_room_config(self.event, room_id)
        if not room_config:
            await self.consumer.send_json(
                ["error", self.content[1], {"message": "Unknown room ID."}]
            )
            return
        if "chat.native" not in [m["type"] for m in room_config["modules"]]:
            await self.consumer.send_json(
                ["error", self.content[1], {"message": "Room does not contain a chat."}]
            )
            return
        await self.consumer.channel_layer.group_add(
            "chat.{}".format(room_id), self.consumer.channel_name
        )
        await self.consumer.send_json(["success", self.content[1], {}])

    async def leave(self):
        room_id = self.content[2]["room"]
        await self.consumer.channel_layer.group_discard(
            "chat.{}".format(room_id), self.consumer.channel_name
        )
        await self.consumer.send_json(["success", self.content[1], {}])

    async def send(self):
        room_id = self.content[2]["room"]
        content = self.content[2]["content"]
        event_type = self.content[2]["event_type"]
        async with aioredis() as redis:
            event_id = await redis.incr("chat.event_id")

        await self.consumer.channel_layer.group_send(
            "chat.{}".format(room_id),
            {
                "type": "chat.event",
                "room": room_id,
                "event_type": event_type,
                "content": content,
                "sender": "user_todo",  # TODO
                "event_id": event_id,
            },
        )
        # TODO: Filter if user is allowed to send this type of message
        await self.consumer.send_json(["success", self.content[1], {}])

    async def publish_event(self):
        # TODO: Filter if user is allowed to see
        await self.consumer.send_json(
            ["chat.event", {k: v for k, v in self.content.items() if k != "type"}]
        )

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.event = self.consumer.scope["url_route"]["kwargs"]["event"]
        if content[0] == "chat.join":
            await self.join()
        elif content[0] == "chat.leave":
            await self.leave()
        elif content[0] == "chat.send":
            await self.send()
        else:
            await self.error("chat.unsupported_command")

    async def dispatch_event(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.event = self.consumer.scope["url_route"]["kwargs"]["event"]
        if content["type"] == "chat.event":
            await self.publish_event()
        else:
            await self.error("chat.unsupported_event")

    async def error(self, code):
        await self.consumer.send_json(["error", self.content[1], {"code": code}])
