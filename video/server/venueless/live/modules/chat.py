import logging
from contextlib import suppress

from venueless.core.permissions import Permission
from venueless.core.services.chat import ChatService
from venueless.core.services.user import get_public_user
from venueless.core.services.world import get_room, get_world
from venueless.live.channels import GROUP_CHAT
from venueless.live.decorators import room_action
from venueless.live.exceptions import ConsumerException

logger = logging.getLogger(__name__)


class ChatModule:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_id = None
        self.channels_subscribed = set()
        self.actions = {
            "join": self.join,
            "leave": self.leave,
            "send": self.send,
            "fetch": self.fetch,
            "subscribe": self.subscribe,
            "unsubscribe": self.unsubscribe,
        }

    async def _subscribe(self):
        self.channels_subscribed.add(self.channel_id)
        await self.consumer.channel_layer.group_add(
            GROUP_CHAT.format(channel=self.channel_id), self.consumer.channel_name
        )
        await self.service.track_subscription(
            self.channel_id, self.consumer.user.id, self.consumer.socket_id
        )
        return {
            "state": None,
            "next_event_id": (await self.service.get_last_id()) + 1,
            "members": await self.service.get_channel_users(self.channel_id),
        }

    async def _unsubscribe(self, clean_volatile_membership=True):
        with suppress(KeyError):
            self.channels_subscribed.remove(self.channel_id)
        if clean_volatile_membership:
            remaining_sockets = await self.service.track_unsubscription(
                self.channel_id, self.consumer.user.id, self.consumer.socket_id
            )
            if remaining_sockets == 0 and await self.service.membership_is_volatile(
                self.channel_id, self.consumer.user.id
            ):
                await self._leave()
        await self.consumer.channel_layer.group_discard(
            GROUP_CHAT.format(channel=self.channel_id), self.consumer.channel_name
        )

    @room_action(
        permission_required=Permission.ROOM_CHAT_READ, module_required="chat.native"
    )
    async def subscribe(self):
        reply = await self._subscribe()
        await self.consumer.send_success(reply)

    @room_action(
        permission_required=Permission.ROOM_CHAT_JOIN, module_required="chat.native"
    )
    async def join(self):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("channel.join.missing_profile")
        reply = await self._subscribe()

        volatile_config = self.module_config.get("volatile", False)
        volatile_client = self.content[2].get("volatile", volatile_config)
        if (
            volatile_client != volatile_config
            and await self.world.has_permission_async(
                user=self.consumer.user,
                room=self.room,
                permission=Permission.ROOM_CHAT_MODERATE,
            )
        ):
            volatile_config = volatile_client

        joined = await self.service.add_channel_user(
            self.channel_id, self.consumer.user.id, volatile=volatile_config
        )
        if joined:
            event = await self.service.create_event(
                channel=str(self.channel_id),
                event_type="channel.member",
                content={
                    "membership": "join",
                    "user": await get_public_user(self.world_id, self.consumer.user.id),
                },
                sender=self.consumer.user,
            )
            await self.consumer.channel_layer.group_send(
                GROUP_CHAT.format(channel=self.channel_id), event,
            )
            await self._broadcast_channel_list()
        await self.consumer.send_success(reply)

    async def _leave(self):
        await self.service.remove_channel_user(self.channel_id, self.consumer.user.id)
        await self.consumer.channel_layer.group_send(
            GROUP_CHAT.format(channel=self.channel_id),
            await self.service.create_event(
                channel=self.channel_id,
                event_type="channel.member",
                content={
                    "membership": "leave",
                    "user": self.consumer.user.serialize_public(),
                },
                sender=self.consumer.user,
            ),
        )
        await self._broadcast_channel_list()

    async def _broadcast_channel_list(self):
        await self.consumer.user_broadcast(
            "chat.channels",
            {
                "channels": await self.service.get_channels_for_user(
                    self.consumer.user.id, is_volatile=False
                )
            },
        )

    @room_action(module_required="chat.native")
    async def leave(self):
        await self._unsubscribe(clean_volatile_membership=False)
        await self._leave()
        await self.consumer.send_success()

    @room_action(module_required="chat.native")
    async def unsubscribe(self):
        await self._unsubscribe()
        await self.consumer.send_success()

    @room_action(
        permission_required=Permission.ROOM_CHAT_READ, module_required="chat.native"
    )
    async def fetch(self):
        count = self.content[2]["count"]
        before_id = self.content[2]["before_id"]
        events = await self.service.get_events(
            self.channel_id, before_id=before_id, count=count
        )
        await self.consumer.send_success({"results": events})

    @room_action(
        permission_required=Permission.ROOM_CHAT_SEND, module_required="chat.native"
    )
    async def send(self):
        content = self.content[2]["content"]
        event_type = self.content[2]["event_type"]
        if event_type != "channel.message":
            raise ConsumerException("chat.unsupported_event_type")
        if content.get("type") != "text":
            raise ConsumerException("chat.unsupported_content_type")

        try:
            event = await self.service.create_event(
                channel=self.channel_id,
                event_type=event_type,
                content=content,
                sender=self.consumer.user,
            )
        except ChatService.NotAChannelMember:
            raise ConsumerException("chat.denied")
        await self.consumer.channel_layer.group_send(
            GROUP_CHAT.format(channel=self.channel_id), event
        )
        await self.consumer.send_success(
            {"event": {k: v for k, v in event.items() if k != "type"}}
        )

    async def publish_event(self):
        world = await get_world(self.world_id)
        room = await get_room(world=world, channel__id=self.content["channel"])
        if not await world.has_permission_async(
            user=self.consumer.user, permission=Permission.ROOM_CHAT_READ, room=room
        ):
            print("no perm")
            return
        await self.consumer.send_json(
            ["chat.event", {k: v for k, v in self.content.items() if k != "type"}]
        )

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.channel_id = self.content[2].get("channel")
        self.world_id = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.world = await get_world(self.world_id)
        self.service = ChatService(self.world_id)
        _, action = content[0].rsplit(".", maxsplit=1)
        if action not in self.actions:
            raise ConsumerException("chat.unsupported_command")
        await self.actions[action]()

    async def dispatch_event(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world_id = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.service = ChatService(self.world_id)
        if self.content["type"] == "chat.event":
            await self.publish_event()
        else:  # pragma: no cover
            logger.warning(
                f'Ignored unknown event {content["type"]}'
            )  # ignore unknown event

    async def dispatch_disconnect(self, consumer, close_code):
        self.consumer = consumer
        self.world_id = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.service = ChatService(self.world_id)

        for channel_id in frozenset(self.channels_subscribed):
            self.channel_id = channel_id
            await self._unsubscribe()
