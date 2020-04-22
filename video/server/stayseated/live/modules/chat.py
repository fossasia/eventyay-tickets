from contextlib import suppress

from stayseated.core.services.chat import ChatService
from stayseated.core.services.user import get_public_user
from stayseated.core.services.world import get_room_config
from stayseated.live.exceptions import ConsumerException


class ChatModule:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_id = None
        self.channels_subscribed = set()
        self.channels_joined = set()
        self.actions = {
            "join": self.join,
            "leave": self.leave,
            "send": self.send,
            "fetch": self.fetch,
            "subscribe": self.subscribe,
            "unsubscribe": self.unsubscribe,
        }

    async def get_room(self):
        room_config = await get_room_config(self.world, self.channel_id)
        if not room_config:
            raise ConsumerException("room.unknown", "Unknown room ID")
        if "chat.native" not in [m["type"] for m in room_config["modules"]]:
            raise ConsumerException("chat.unknown", "Room does not contain a chat.")
        return room_config

    async def _subscribe(self):
        self.channels_subscribed.add(self.channel_id)
        await self.consumer.channel_layer.group_add(
            "chat.{}".format(self.channel_id), self.consumer.channel_name
        )
        return {
            "state": None,
            "next_event_id": (await self.service.get_last_id()) + 1,
            "members": await self.service.get_channel_users(self.channel_id),
        }

    async def _unsubscribe(self):
        with suppress(KeyError):
            self.channels_subscribed.remove(self.channel_id)
        await self.consumer.channel_layer.group_discard(
            f"chat.{self.channel_id}", self.consumer.channel_name
        )

    async def subscribe(self):
        await self.get_room()
        reply = await self._subscribe()
        await self.consumer.send_success(reply)

    async def join(self):
        if not self.consumer.user.get("profile", {}).get("display_name"):
            raise ConsumerException("channel.join.missing_profile")
        await self.get_room()
        reply = await self._subscribe()
        self.channels_joined.add(self.channel_id)
        await self.consumer.channel_layer.group_send(
            f"chat.{self.channel_id}",
            await self.service.create_event(
                channel=self.channel_id,
                event_type="channel.member",
                content={
                    "membership": "join",
                    "user": await get_public_user(self.world, self.consumer.user["id"]),
                },
                sender=self.consumer.user["id"],
            ),
        )
        await self.service.add_channel_user(self.channel_id, self.consumer.user["id"])
        await self.consumer.send_success(reply)

    async def _leave(self):
        await self.service.remove_channel_user(
            self.channel_id, self.consumer.user["id"]
        )
        await self.consumer.channel_layer.group_send(
            f"chat.{self.channel_id}",
            await self.service.create_event(
                channel=self.channel_id,
                event_type="channel.member",
                content={
                    "membership": "leave",
                    "user": await get_public_user(self.world, self.consumer.user["id"]),
                },
                sender=self.consumer.user["id"],
            ),
        )
        try:
            self.channels_joined.remove(self.channel_id)
        except KeyError:  # pragma: no cover
            pass

    async def leave(self):
        await self.get_room()
        await self._leave()
        await self.consumer.send_success()

    async def unsubscribe(self):
        # unsubscribe is a leave if we're joined, and a simple unsubscribe otherwise
        await self.get_room()
        await self._unsubscribe()
        if self.channel_id in self.channels_joined:
            await self._leave()
        await self.consumer.send_success()

    async def fetch(self):
        await self.get_room()
        count = self.content[2]["count"]
        before_id = self.content[2]["before_id"]
        events = await self.service.get_events(
            self.channel_id, before_id=before_id, count=count
        )
        # TODO: Filter if user is allowed to see
        await self.consumer.send_success({"results": events})

    async def send(self):
        await self.get_room()
        content = self.content[2]["content"]
        event_type = self.content[2]["event_type"]
        # TODO: Filter if user is allowed to send this type of message
        await self.consumer.channel_layer.group_send(
            f"chat.{self.channel_id}",
            await self.service.create_event(
                channel=self.channel_id,
                event_type=event_type,
                content=content,
                sender=self.consumer.user["id"],
            ),
        )
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
        self.world = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.service = ChatService(self.world)
        _, action = content[0].rsplit(".", maxsplit=1)
        if action not in self.actions:
            raise ConsumerException("chat.unsupported_command")
        await self.actions[action]()

    async def dispatch_event(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.service = ChatService(self.world)
        await self.publish_event()

    async def dispatch_disconnect(self, consumer, close_code):
        self.consumer = consumer
        self.world = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.service = ChatService(self.world)

        for channel_id in frozenset(self.channels_joined):
            self.channel_id = channel_id
            await self._leave()

        for channel_id in frozenset(self.channels_subscribed):
            self.channel_id = channel_id
            await self._unsubscribe()
