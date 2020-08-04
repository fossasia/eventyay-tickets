import asyncio
import logging
import time

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework import serializers
from sentry_sdk import add_breadcrumb, configure_scope

from venueless.core.models import Channel, Room
from venueless.core.permissions import Permission
from venueless.core.services.reactions import store_reaction
from venueless.core.services.room import end_view, start_view
from venueless.core.services.world import (
    create_room,
    get_room_config_for_user,
    get_rooms,
    notify_world_change,
)
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


class RoomConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = (
            "id",
            "trait_grants",
            "module_config",
            "picture",
            "name",
            "description",
            "sorting_priority",
            "pretalx_id",
        )


class RoomModule(BaseModule):
    prefix = "room"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_views = {}

    @command("enter")
    @room_action(permission_required=Permission.ROOM_VIEW)
    async def enter_room(self, body):
        await self.consumer.channel_layer.group_add(
            GROUP_ROOM.format(id=self.room.pk), self.consumer.channel_name
        )
        if self.consumer.world.config.get("track_room_views", True):
            self.current_views[self.room] = await start_view(
                self.room, self.consumer.user
            )
        await self.consumer.send_success({})
        if settings.SENTRY_DSN:
            add_breadcrumb(
                category="room",
                message=f"Entered room {self.room.pk} ({self.room.name})",
                level="info",
            )
            with configure_scope() as scope:
                scope.set_extra("last_room", str(self.room.pk))

    async def _leave_room(self, room):
        await self.consumer.channel_layer.group_discard(
            GROUP_ROOM.format(id=room.pk), self.consumer.channel_name
        )
        if room in self.current_views:
            await end_view(self.current_views[room])
            del self.current_views[room]

    @command("leave")
    @room_action()
    async def leave_room(self, body):
        await self._leave_room(self.room)
        await self.consumer.send_success({})

    async def dispatch_disconnect(self, close_code):
        for room in list(self.current_views.keys()):
            await self._leave_room(room)

    @command("react")
    @room_action(permission_required=Permission.ROOM_VIEW)
    async def send_reaction(self, body):
        reaction = body.get("reaction")
        if reaction not in (
            "+1",
            "clap",
            "heart",
            "open_mouth",
            "rolling_on_the_floor_laughing",
        ):
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
            tr.hsetnx(redis_key, "tick", int(time.time()))
            tr.hget(redis_key, "tick")
            tr.hincrby(redis_key, reaction, 1)
            tick_new, tick_start, _ = await tr.execute()

            await self.consumer.send_success({})

            if tick_new or time.time() - int(tick_start.decode()) > 3:
                # We're the first one to react since the last tick! It's our job to wait for the length of a tick, then
                # distribute the value to everyone.
                await asyncio.sleep(1)

                tr = redis.multi_exec()
                tr.hgetall(redis_key)
                tr.delete(redis_key)
                val, _ = await tr.execute()
                if not val:
                    return
                await self.consumer.channel_layer.group_send(
                    GROUP_ROOM.format(id=self.room.pk),
                    {
                        "type": "room.reaction",
                        "reactions": {
                            k.decode(): int(v.decode())
                            for k, v in val.items()
                            if k.decode() != "tick"
                        },
                        "room": str(body["room"]),
                    },
                )
                for k, v in val.items():
                    if k.decode() != "tick":
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

    @command("config.list")
    @require_world_permission(Permission.ROOM_UPDATE)
    async def rooms_list(self, body):
        rooms = await database_sync_to_async(get_rooms)(self.consumer.world, user=None)
        await self.consumer.send_success(RoomConfigSerializer(rooms, many=True).data)

    @command("config.get")
    @room_action(permission_required=Permission.ROOM_UPDATE)
    async def config_get(self, body):
        await self.consumer.send_success(RoomConfigSerializer(self.room).data)

    @command("config.patch")
    @room_action(permission_required=Permission.ROOM_UPDATE)
    async def config_patch(self, body):
        s = RoomConfigSerializer(self.room, data=body, partial=True)
        if s.is_valid():
            update_fields = set()
            for f in s.fields.keys():
                if f in body:
                    setattr(self.room, f, s.validated_data[f])
                    update_fields.add(f)

            await database_sync_to_async(self.room.save)(
                update_fields=list(update_fields)
            )
            if "chat.native" in set(m["type"] for m in self.room.module_config):
                await database_sync_to_async(Channel.objects.get_or_create)(
                    world_id=self.consumer.world.pk, room=self.room
                )
            await self.consumer.send_success(RoomConfigSerializer(self.room).data)
            await notify_world_change(self.consumer.world.id)
        else:
            await self.consumer.send_error(code="config.invalid")

    @command("delete")
    @room_action(permission_required=Permission.ROOM_DELETE)
    async def delete(self, body):
        self.room.deleted = True
        await database_sync_to_async(self.room.save)(update_fields=["deleted"])
        await self.consumer.send_success()
        await get_channel_layer().group_send(
            f"world.{self.consumer.world.id}",
            {"type": "room.delete", "room": str(self.room.id)},
        )
