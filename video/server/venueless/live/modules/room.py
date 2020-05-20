import asyncio
import logging

from django.core.exceptions import ValidationError

from venueless.core.permissions import Permission
from venueless.core.services.reactions import store_reaction
from venueless.core.services.world import (
    create_room,
    get_room_config_for_user,
    get_world,
)
from venueless.core.utils.redis import aioredis
from venueless.live.channels import GROUP_ROOM
from venueless.live.decorators import require_world_permission, room_action
from venueless.live.exceptions import ConsumerException

logger = logging.getLogger(__name__)


class RoomModule:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {
            "room.create": self.create_room,
            "room.enter": self.enter_room,
            "room.leave": self.leave_room,
            "room.react": self.send_reaction,
        }

    @room_action(permission_required=Permission.ROOM_VIEW)
    async def enter_room(self):
        await self.consumer.channel_layer.group_add(
            GROUP_ROOM.format(id=self.room.pk), self.consumer.channel_name
        )
        await self.consumer.send_success({})

    @room_action()
    async def leave_room(self):
        await self.consumer.channel_layer.group_discard(
            GROUP_ROOM.format(id=self.room.pk), self.consumer.channel_name
        )
        await self.consumer.send_success({})

    @room_action(permission_required=Permission.ROOM_VIEW)
    async def send_reaction(self):
        reaction = self.content[2].get("reaction")
        if reaction not in ("+1", "clap", "heart", "open_mouth"):
            raise ConsumerException(
                code="room.unknown_reaction", message="Unknown reaction"
            )

        redis_key = f"reactions:{self.world_id}:{self.room_id}"
        redis_debounce_key = f"reactions:{self.world_id}:{self.room_id}:{reaction}:{self.consumer.user.id}"

        # We want to send reactions out to anyone, but we want to aggregate them over short time frames ("ticks") to
        # make sure we do not send 500 messages if 500 people react in the same second, but just one.
        async with aioredis() as redis:
            debounce = await redis.set(
                redis_debounce_key, "1", expire=2, exist=redis.SET_IF_NOT_EXIST
            )
            if not debounce:
                # User reacted in the 2 seconds, let's ignore this.
                await self.consumer.send_success({})
                return

            # First, increase the number of reactions
            tr = redis.multi_exec()
            tr.exists(redis_key)
            tr.hincrby(redis_key, reaction, 1)
            tick_running, _ = await tr.execute()

            await self.consumer.send_success({})

            if not tick_running:
                # We're the first one to react since the last tick! It's our job to wait for the length of a tick, then
                # distribute the value to everyone.
                await asyncio.sleep(1)

                tr = redis.multi_exec()
                tr.hgetall(redis_key)
                tr.delete(redis_key)
                val, _ = await tr.execute()
                await self.consumer.channel_layer.group_send(
                    GROUP_ROOM.format(id=self.room.pk),
                    {
                        "type": "room.reaction",
                        "reactions": {
                            k.decode(): int(v.decode()) for k, v in val.items()
                        },
                        "room": str(self.room_id),
                    },
                )
                for k, v in val.items():
                    await store_reaction(self.room_id, k.decode(), int(v.decode()))
            # else: We're just contributing to the reaction counter that someone else started.

    @require_world_permission(Permission.WORLD_ROOMS_CREATE)
    async def create_room(self):
        try:
            room = await create_room(self.world, self.content[-1], self.consumer.user)
        except ValidationError as e:
            await self.consumer.send_error(code="room.invalid", message=str(e))
        else:
            await self.consumer.send_success(room)

    async def push_reaction(self):
        await self.consumer.send_json(
            [
                self.content["type"],
                {k: v for k, v in self.content.items() if k != "type"},
            ]
        )

    async def push_room_info(self):
        world = await get_world(self.world_id)
        if not await world.has_permission_async(
            user=self.consumer.user, permission=Permission.ROOM_VIEW
        ):
            return
        await self.consumer.send_json(
            [
                self.content["type"],
                await get_room_config_for_user(
                    self.content["room"], self.world_id, self.consumer.user
                ),
            ]
        )

    async def dispatch_event(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world_id = self.consumer.scope["url_route"]["kwargs"]["world"]
        if self.content["type"] == "room.create":
            await self.push_room_info()
        elif self.content["type"] == "room.reaction":
            await self.push_reaction()
        else:  # pragma: no cover
            logger.warning(
                f'Ignored unknown event {content["type"]}'
            )  # ignore unknown event

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world_id = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.world = await get_world(self.world_id)
        self.room_id = self.content[2].get("room")
        action = content[0]
        if action not in self.actions:
            raise ConsumerException("room.unsupported_command")
        await self.actions[action]()
