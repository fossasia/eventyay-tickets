import logging
from contextlib import suppress

from channels.db import database_sync_to_async
from sentry_sdk import configure_scope

from venueless.core.permissions import Permission
from venueless.core.services.chat import ChatService
from venueless.core.services.world import get_room
from venueless.live.channels import GROUP_CHAT
from venueless.live.decorators import command, event, room_action
from venueless.live.exceptions import ConsumerException
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class ChatModule(BaseModule):
    prefix = "chat"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_id = None
        self.channels_subscribed = set()
        self.service = ChatService(self.consumer.world.id)

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
            "members": await self.service.get_channel_users(
                self.channel_id,
                include_admin_info=await self.consumer.world.has_permission_async(
                    user=self.consumer.user, permission=Permission.WORLD_USERS_MANAGE
                ),
            ),
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

    @command("subscribe")
    @room_action(
        permission_required=Permission.ROOM_CHAT_READ, module_required="chat.native"
    )
    async def subscribe(self, body):
        reply = await self._subscribe()
        await self.consumer.send_success(reply)

    @command("join")
    @room_action(
        permission_required=Permission.ROOM_CHAT_JOIN, module_required="chat.native"
    )
    async def join(self, body):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("channel.join.missing_profile")
        reply = await self._subscribe()

        volatile_config = self.module_config.get("volatile", False)
        volatile_client = body.get("volatile", volatile_config)
        if (
            volatile_client != volatile_config
            and await self.consumer.world.has_permission_async(
                user=self.consumer.user,
                room=self.room,
                permission=Permission.ROOM_CHAT_MODERATE,
            )
        ):
            volatile_config = volatile_client

        joined = await self.service.add_channel_user(
            self.channel_id, self.consumer.user, volatile=volatile_config
        )
        if joined:
            event = await self.service.create_event(
                channel_id=str(self.channel_id),
                event_type="channel.member",
                content={
                    "membership": "join",
                    "user": self.consumer.user.serialize_public(),
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
                channel_id=self.channel_id,
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
        await self.consumer.user.refresh_from_db_if_outdated()
        await self.consumer.user_broadcast(
            "chat.channels",
            {
                "channels": await database_sync_to_async(
                    self.service.get_channels_for_user
                )(self.consumer.user.id, is_volatile=False)
            },
        )

    @command("leave")
    @room_action(module_required="chat.native")
    async def leave(self, body):
        await self._unsubscribe(clean_volatile_membership=False)
        await self._leave()
        await self.consumer.send_success()

    @command("unsubscribe")
    @room_action(module_required="chat.native")
    async def unsubscribe(self, body):
        await self._unsubscribe()
        await self.consumer.send_success()

    @command("fetch")
    @room_action(
        permission_required=Permission.ROOM_CHAT_READ, module_required="chat.native"
    )
    async def fetch(self, body):
        count = body["count"]
        before_id = body["before_id"]
        events = await self.service.get_events(
            self.channel_id, before_id=before_id, count=count
        )
        await self.consumer.send_success({"results": events})

    @command("send")
    @room_action(
        permission_required=Permission.ROOM_CHAT_SEND, module_required="chat.native"
    )
    async def send(self, body):
        content = body["content"]
        event_type = body["event_type"]
        if event_type != "channel.message":
            raise ConsumerException("chat.unsupported_event_type")
        if not (
            content.get("type") == "text"
            or (content.get("type") == "deleted" and "replaces" in body)
        ):
            raise ConsumerException("chat.unsupported_content_type")

        if body.get("replaces"):
            other_message = await self.service.get_event(
                pk=body["replaces"], channel_id=self.channel_id,
            )
            if self.consumer.user.id != other_message.sender_id:
                # Users may only edit messages by other users if they are mods,
                # and even then only delete them
                is_moderator = await self.consumer.world.has_permission_async(
                    user=self.consumer.user,
                    room=self.room,
                    permission=Permission.ROOM_CHAT_MODERATE,
                )
                if body["content"]["type"] != "deleted" or not is_moderator:
                    raise ConsumerException("chat.denied")
            await self.service.update_event(other_message, new_content=content)

        if content.get("type") == "text" and not content.get("body"):
            raise ConsumerException("chat.empty")

        try:
            event = await self.service.create_event(
                channel_id=self.channel_id,
                event_type=event_type,
                content=content,
                sender=self.consumer.user,
                replaces=body.get("replaces", None),
            )
        except ChatService.NotAChannelMember:
            raise ConsumerException("chat.denied")
        await self.consumer.channel_layer.group_send(
            GROUP_CHAT.format(channel=self.channel_id), event
        )
        await self.consumer.send_success(
            {"event": {k: v for k, v in event.items() if k != "type"}}
        )

    @event("event", refresh_world=True, refresh_user=True)
    async def publish_event(self, body):
        room = self.consumer.room_cache.get(("channel", body["channel"]))
        if room:
            await room.refresh_from_db_if_outdated()
        else:
            room = await get_room(
                world=self.consumer.world, channel__id=body["channel"]
            )
            self.consumer.room_cache["channel", body["channel"]] = room

        if not await self.consumer.world.has_permission_async(
            user=self.consumer.user, permission=Permission.ROOM_CHAT_READ, room=room
        ):
            return
        await self.consumer.send_json(
            ["chat.event", {k: v for k, v in body.items() if k != "type"}]
        )

    async def dispatch_command(self, content):
        self.channel_id = content[2].get("channel")
        with configure_scope() as scope:
            scope.set_extra("last_channel", str(self.channel_id))
        return await super().dispatch_command(content)

    async def dispatch_disconnect(self, close_code):
        for channel_id in frozenset(self.channels_subscribed):
            self.channel_id = channel_id
            await self._unsubscribe()
