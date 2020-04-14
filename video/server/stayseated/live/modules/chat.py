from stayseated.core.services.chat import (
    add_channel_user,
    get_channel_users,
    remove_channel_user,
)
from stayseated.core.services.event import get_room_config
from stayseated.core.services.user import get_public_user
from stayseated.core.utils.redis import aioredis
from stayseated.live.exceptions import ConsumerException


class ChatModule:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_id = None
        self.actions = {
            "join": self.join,
            "leave": self.leave,
            "send": self.send,
            "subscribe": self.subscribe,
            "unsubscribe": self.unsubscribe,
        }

    async def get_room(self):
        room_config = await get_room_config(self.event, self.channel_id)
        if not room_config:
            raise ConsumerException("room.unknown", "Unknown room ID")
        if "chat.native" not in [m["type"] for m in room_config["modules"]]:
            raise ConsumerException("chat.unknown", "Room does not contain a chat.")
        return room_config

    async def _subscribe(self):
        await self.consumer.channel_layer.group_add(
            "chat.{}".format(self.channel_id), self.consumer.channel_name
        )
        return {"state": None, "members": await get_channel_users(self.channel_id)}

    async def _leave(self):
        await remove_channel_user(self.channel_id, self.consumer.user["user_id"])
        async with aioredis() as redis:
            event_id = await redis.incr("chat.event_id")
        await self.consumer.channel_layer.group_send(
            "chat.{}".format(self.channel_id),
            {
                "type": "chat.event",
                "channel": self.channel_id,
                "event_type": "channel.member",
                "membership": "leave",
                "user": await get_public_user(self.consumer.user["user_id"]),
                "sender": self.consumer.user["user_id"],
                "event_id": event_id,
            },
        )

    async def subscribe(self):
        await self.get_room()
        reply = await self._subscribe()
        await self.consumer.send_success(reply)

    async def join(self):
        if not self.consumer.user.get("profile"):
            raise ConsumerException("channel.join.missing_profile")
        await self.get_room()
        reply = await self._subscribe()
        async with aioredis() as redis:
            event_id = await redis.incr("chat.event_id")
        await self.consumer.channel_layer.group_send(
            f"chat.{self.channel_id}",
            {
                "type": "chat.event",
                "channel": self.channel_id,
                "event_type": "channel.member",
                "membership": "join",
                "user": await get_public_user(self.consumer.user["user_id"]),
                "sender": self.consumer.user["user_id"],
                "event_id": event_id,
            },
        )
        await add_channel_user(self.channel_id, self.consumer.user["user_id"])
        await self.consumer.send_success(reply)

    async def leave(self):
        await self.get_room()
        await self._leave()
        await self.consumer.send_success()

    async def unsubscribe(self):
        await self.get_room()
        await self.consumer.channel_layer.group_discard(
            f"chat.{self.channel_id}", self.consumer.channel_name
        )
        await self._leave()
        await self.consumer.send_success()

    async def send(self):
        await self.get_room()
        content = self.content[2]["content"]
        event_type = self.content[2]["event_type"]
        async with aioredis() as redis:
            event_id = await redis.incr("chat.event_id")

        await self.consumer.channel_layer.group_send(
            f"chat.{self.channel_id}",
            {
                "type": "chat.event",
                "channel": self.channel_id,
                "event_type": event_type,
                "content": content,
                "sender": self.consumer.user["user_id"],
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
        self.channel_id = self.content[2].get("channel")
        self.event = self.consumer.scope["url_route"]["kwargs"]["event"]
        _, action = content[0].rsplit(".", maxsplit=1)
        if action not in self.actions:
            raise ConsumerException("chat.unsupported_command")
        await self.actions[action]()

    async def dispatch_event(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.event = self.consumer.scope["url_route"]["kwargs"]["event"]
        await self.publish_event()
