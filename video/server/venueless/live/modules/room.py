import asyncio
import logging
import time

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.exceptions import ValidationError
from sentry_sdk import add_breadcrumb, configure_scope

from venueless.core.models.room import RoomConfigSerializer, approximate_view_number
from venueless.core.permissions import Permission
from venueless.core.services.poll import get_polls, get_voted_polls
from venueless.core.services.reactions import store_reaction
from venueless.core.services.room import (
    delete_room,
    end_view,
    reorder_rooms,
    save_room,
    start_view,
)
from venueless.core.services.world import (
    create_room,
    get_room_config_for_user,
    get_rooms,
    notify_world_change,
)
from venueless.core.utils.redis import aioredis
from venueless.live.channels import (
    GROUP_ROOM,
    GROUP_ROOM_POLL_MANAGE,
    GROUP_ROOM_POLL_READ,
    GROUP_ROOM_POLL_RESULTS,
    GROUP_ROOM_QUESTION_MODERATE,
    GROUP_ROOM_QUESTION_READ,
    GROUP_WORLD,
)
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_views = {}

    @command("enter")
    @room_action(permission_required=Permission.ROOM_VIEW)
    async def enter_room(self, body):
        await self.consumer.channel_layer.group_add(
            GROUP_ROOM.format(id=self.room.pk), self.consumer.channel_name
        )
        permissions = {
            Permission.ROOM_QUESTION_READ: GROUP_ROOM_QUESTION_READ,
            Permission.ROOM_QUESTION_MODERATE: GROUP_ROOM_QUESTION_MODERATE,
            Permission.ROOM_POLL_READ: GROUP_ROOM_POLL_READ,
            Permission.ROOM_POLL_MANAGE: GROUP_ROOM_POLL_MANAGE,
        }
        for permission, group_name in permissions.items():
            if await self.consumer.world.has_permission_async(
                user=self.consumer.user,
                room=self.room,
                permission=permission,
            ):
                await self.consumer.channel_layer.group_add(
                    group_name.format(id=self.room.pk),
                    self.consumer.channel_name,
                )

        if await self.consumer.world.has_permission_async(
            user=self.consumer.user,
            room=self.room,
            permission=Permission.ROOM_POLL_VOTE,
        ):
            # For polls, we have to add users to all groups they have already voted for
            voted_polls = await get_voted_polls(self.room, self.user)
            for poll in voted_polls:
                await self.consumer.channel_layer.group_add(
                    GROUP_ROOM_POLL_RESULTS.format(id=self.room.pk, poll=poll),
                    self.consumer.channel_name,
                )
        await self.consumer.send_success({})

        self.current_views[self.room], actual_view_count = await start_view(
            self.room,
            self.consumer.user,
            delete=not self.consumer.world.config.get("track_room_views", True),
        )
        await self._update_view_count(self.room, actual_view_count)

        if settings.SENTRY_DSN:
            add_breadcrumb(
                category="room",
                message=f"Entered room {self.room.pk} ({self.room.name})",
                level="info",
            )
            with configure_scope() as scope:
                scope.set_extra("last_room", str(self.room.pk))

    async def _leave_room(self, room):
        group_names = [
            GROUP_ROOM,
            GROUP_ROOM_QUESTION_MODERATE,
            GROUP_ROOM_QUESTION_READ,
            GROUP_ROOM_POLL_MANAGE,
            GROUP_ROOM_POLL_READ,
        ]
        for group_name in group_names:
            await self.consumer.channel_layer.group_discard(
                group_name.format(id=room.pk), self.consumer.channel_name
            )
        for poll in await get_polls(self.room):
            await self.consumer.channel_layer.group_discard(
                GROUP_ROOM_POLL_RESULTS.format(id=room.pk, poll=poll["id"]),
                self.consumer.channel_name,
            )
        if room in self.current_views:
            actual_view_count = await end_view(
                self.current_views[room],
                delete=not self.consumer.world.config.get("track_room_views", True),
            )
            del self.current_views[room]
            await self._update_view_count(room, actual_view_count)

    async def _update_view_count(self, room, actual_view_count):
        async with aioredis() as redis:
            next_value = approximate_view_number(actual_view_count)
            prev_value = await redis.getset(
                f"room:approxcount:known:{room.pk}", next_value
            )
            if prev_value:
                prev_value = prev_value.decode()
            if prev_value != next_value:
                await redis.expire(f"room:approxcount:known:{room.pk}", 900)
                await self.consumer.channel_layer.group_send(
                    GROUP_WORLD.format(id=self.consumer.world.pk),
                    {
                        "type": "world.user_count_change",
                        "room": str(room.pk),
                        "users": next_value,
                    },
                )

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
            Permission.WORLD_ROOMS_CREATE_EXHIBITION,
            Permission.ROOM_UPDATE,
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
            [
                body["type"],
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("create", refresh_user=True, refresh_world=True)
    async def push_room_info(self, body):
        conf = await get_room_config_for_user(
            body["room"], self.consumer.world.id, self.consumer.user
        )
        if "room:view" not in conf["permissions"]:
            return
        await self.consumer.send_json(
            [
                body["type"],
                conf,
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
        old = RoomConfigSerializer(self.room).data
        s = RoomConfigSerializer(self.room, data=body, partial=True)
        if s.is_valid():
            update_fields = set()
            for f in s.fields.keys():
                if f in body:
                    setattr(self.room, f, s.validated_data[f])
                    update_fields.add(f)

            new = await save_room(
                self.consumer.world,
                self.room,
                list(update_fields),
                old_data=old,
                by_user=self.consumer.user,
            )
            await self.consumer.send_success(new)
            await notify_world_change(self.consumer.world.id)
        else:
            await self.consumer.send_error(code="config.invalid")

    @command("config.reorder")
    @require_world_permission(Permission.ROOM_UPDATE)
    async def config_reorder(self, body):
        await reorder_rooms(self.consumer.world, body, self.consumer.user)
        rooms = await database_sync_to_async(get_rooms)(self.consumer.world, user=None)
        await self.consumer.send_success(RoomConfigSerializer(rooms, many=True).data)
        await notify_world_change(self.consumer.world.id)

    @command("delete")
    @room_action(permission_required=Permission.ROOM_DELETE)
    async def delete(self, body):
        self.room.deleted = True
        await delete_room(self.consumer.world, self.room, by_user=self.consumer.user)
        await self.consumer.send_success()
        await get_channel_layer().group_send(
            f"world.{self.consumer.world.id}",
            {"type": "room.delete", "room": str(self.room.id)},
        )

    @event("delete")
    async def push_room_delete(self, body):
        await self.consumer.send_json([body["type"], {"id": body["room"]}])

    @command("schedule")
    @room_action(permission_required=Permission.ROOM_ANNOUNCE)
    async def change_schedule_data(self, body):
        old = RoomConfigSerializer(self.room).data
        data = body.get("schedule_data")
        if data and not all(key in ["title", "session"] for key in data.keys()):
            raise ConsumerException(
                code="room.unknown_schedule_data", message="Unknown schedule data"
            )

        await self.consumer.send_success({})
        self.room.schedule_data = data
        await save_room(
            self.consumer.world,
            self.room,
            ["schedule_data"],
            by_user=self.consumer.user,
            old_data=old,
        )
        await self.consumer.channel_layer.group_send(
            GROUP_ROOM.format(id=self.room.pk),
            {"type": "room.schedule", "schedule_data": data, "room": str(self.room.pk)},
        )

    @event("schedule", refresh_world=True)
    async def push_schedule_data(self, body):
        config = await get_room_config_for_user(
            body["room"], self.consumer.world.id, self.consumer.user
        )
        if "room:view" not in config["permissions"]:
            return
        await self.consumer.send_json(
            [
                body["type"],
                {"room": config["id"], "schedule_data": config.get("schedule_data")},
            ]
        )
