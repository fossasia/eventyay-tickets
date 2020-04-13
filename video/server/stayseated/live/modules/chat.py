from stayseated.core.services.chat import (
    add_channel_user,
    get_channel_users,
    remove_channel_user,
)
from stayseated.core.services.event import get_room_config
from stayseated.core.utils.redis import aioredis
from stayseated.live.exceptions import ConsumerException


class ChatModule:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {
            "join": self.join,
            "leave": self.leave,
            "send": self.send,
            "subscribe": self.subscribe,
            "unsubscribe": self.unsubscribe,
        }

    async def get_room(self):
        channel_id = self.content[2]["channel"]
        room_config = await get_room_config(self.event, channel_id)
        if not room_config:
            raise ConsumerException("room.unknown", "Unknown room ID")
        if "chat.native" not in [m["type"] for m in room_config["modules"]]:
            raise ConsumerException("chat.unknown", "Room does not contain a chat.")
        return channel_id, room_config

    async def _subscribe(self, channel_id):
        await self.consumer.channel_layer.group_add(
            "chat.{}".format(channel_id), self.consumer.channel_name
        )
        return {"state": None, "members": await get_channel_users(channel_id)}

    async def _leave(self, channel_id):
        # TODO: send notification
        await remove_channel_user(
            channel_id, self.consumer.scope["session"]["user"]["user_id"]
        )

    async def subscribe(self):
        print("subscribing")
        channel_id, _ = await self.get_room()
        reply = await self._subscribe(channel_id)
        print(reply)
        await self.consumer.send_success(reply)

    async def join(self):
        # TODO: send notification
        if not self.consumer.scope["session"]["user"].get("public_name"):
            raise ConsumerException("channel.join.missing_name")
        channel_id, _ = await self.get_room()
        reply = await self._subscribe(channel_id)
        await add_channel_user(
            channel_id, self.consumer.scope["session"]["user"]["user_id"]
        )
        await self.consumer.send_success(reply)

    async def leave(self):
        channel_id, _ = await self.get_room()
        await self._leave(channel_id)
        await self.consumer.send_success()

    async def unsubscribe(self):
        channel_id, _ = await self.get_room()
        await self.consumer.channel_layer.group_discard(
            "chat.{}".format(channel_id), self.consumer.channel_name
        )
        await self._leave(channel_id)
        await self.consumer.send_success()

    async def send(self):
        channel_id, _ = await self.get_room()
        content = self.content[2]["content"]
        event_type = self.content[2]["event_type"]
        async with aioredis() as redis:
            event_id = await redis.incr("chat.event_id")

        await self.consumer.channel_layer.group_send(
            "chat.{}".format(channel_id),
            {
                "type": "chat.event",
                "channel": channel_id,
                "event_type": event_type,
                "content": content,
                "sender": "user_todo",  # TODO
                "event_id": event_id,
            },
        )
        # TODO: Filter if user is allowed to send this type of message
        await self.consumer.send_success()

    async def publish_event(self):
        # TODO: Filter if user is allowed to see
        await self.consumer.send_json(
            ["chat.event", {k: v for k, v in self.content.items() if k != "type"}]
        )

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.event = self.consumer.scope["url_route"]["kwargs"]["event"]
        _, action = content[0].rsplit(".", maxsplit=1)
        if action not in self.actions:
            raise ConsumerException("chat.unsupported_command")
        await self.actions[action]()

    async def dispatch_event(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.event = self.consumer.scope["url_route"]["kwargs"]["event"]
        # if content["type"] == "chat.event":
        await self.publish_event()
