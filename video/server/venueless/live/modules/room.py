import asyncio
import logging

from django.core.exceptions import ValidationError

from venueless.core.permissions import Permission
from venueless.core.services.reactions import store_reaction
from venueless.core.services.world import create_room, get_room_config_for_user
from venueless.core.utils.redis import aioredis
from venueless.live.channels import GROUP_ROOM
from venueless.live.decorators import (
    command,
    event,
    require_world_permission,
    room_action,
)
from venueless.live.exceptions import ConsumerException
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class RoomModule(BaseModule):
    prefix = "room"

    @command("enter")
    @room_action(permission_required=Permission.ROOM_VIEW)
    async def enter_room(self, body):
        await self.consumer.channel_layer.group_add(
            GROUP_ROOM.format(id=self.room.pk), self.consumer.channel_name
        )
        await self.consumer.send_success({})

    @command("leave")
    @room_action()
    async def leave_room(self, body):
        await self.consumer.channel_layer.group_discard(
            GROUP_ROOM.format(id=self.room.pk), self.consumer.channel_name
        )
        await self.consumer.send_success({})

    @command("react")
    @room_action(permission_required=Permission.ROOM_VIEW)
    async def send_reaction(self, body):
        reaction = body.get("reaction")
        if reaction not in ("+1", "clap", "heart", "open_mouth"):
            raise ConsumerException(
                code="room.unknown_reaction", message="Unknown reaction"
            )

        redis_key = f"reactions:{self.consumer.world.id}:{body['room']}"
        redis_debounce_key = f"reactions:{self.consumer.world.id}:{body['room']}:{reaction}:{self.consumer.user.id}"

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
                        "room": str(body["room"]),
                    },
                )
                for k, v in val.items():
                    await store_reaction(body["room"], k.decode(), int(v.decode()))
            # else: We're just contributing to the reaction counter that someone else started.

    @command("create")
    @require_world_permission(
        [
            Permission.WORLD_ROOMS_CREATE_STAGE,
            Permission.WORLD_ROOMS_CREATE_BBB,
            Permission.WORLD_ROOMS_CREATE_CHAT,
        ]
    )
    async def create_room(self, body):
        try:
            room = await create_room(self.consumer.world, body, self.consumer.user)
        except ValidationError as e:
            await self.consumer.send_error(
                code=f"room.invalid.{e.code}", message=str(e)
            )
        else:
            await self.consumer.send_success(room)

    @event("reaction")
    async def push_reaction(self, body):
        await self.consumer.send_json(
            [body["type"], {k: v for k, v in body.items() if k != "type"},]
        )

    @event("create", refresh_user=True, refresh_world=True)
    async def push_room_info(self, body):
        await self.consumer.world.refresh_from_db_if_outdated()
        await self.consumer.user.refresh_from_db_if_outdated()
        if not await self.consumer.world.has_permission_async(
            user=self.consumer.user, permission=Permission.ROOM_VIEW
        ):
            return
        await self.consumer.send_json(
            [
                body["type"],
                await get_room_config_for_user(
                    body["room"], self.consumer.world.id, self.consumer.user
                ),
            ]
        )
