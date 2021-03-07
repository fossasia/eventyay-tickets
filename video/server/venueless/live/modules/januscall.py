import json
import uuid

from aioredis_lock import RedisLock
from channels.db import database_sync_to_async
from django.conf import settings
from sentry_sdk import capture_exception

from venueless.core.models import JanusServer
from venueless.core.permissions import Permission
from venueless.core.services import turn
from venueless.core.services.janus import (
    JanusError,
    choose_server,
    create_videoroom,
    videoroom_exists,
)
from venueless.core.services.roulette import is_member_of_roulette_call
from venueless.core.services.user import get_public_user
from venueless.core.utils.redis import aioredis
from venueless.live.decorators import command, require_world_permission, room_action
from venueless.live.exceptions import ConsumerException
from venueless.live.modules.base import BaseModule


class JanusCallModule(BaseModule):
    prefix = "januscall"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @database_sync_to_async
    def _servers(self):
        return choose_server(self.consumer.world), turn.choose_server(
            self.consumer.world
        )

    @command("room_url")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def room_url(self, body):
        await self.consumer.send_success(
            await self._get_or_create_janus_room(
                f"room:{self.room.id}", audiobridge=True
            )
        )

    @command("channel_url")
    async def channel_url(self, body):
        channel_id = body.get("channel")
        if not await self.consumer.user.is_member_of_channel_async(channel_id):
            raise ConsumerException("janus.denied")
        await self.consumer.send_success(
            await self._get_or_create_janus_room(f"channel:{channel_id}")
        )

    @command("roulette_url")
    async def roulette_url(self, body):
        call_id = body.get("call_id")
        if not await is_member_of_roulette_call(call_id, self.consumer.user):
            raise ConsumerException("janus.denied")
        await self.consumer.send_success(
            await self._get_or_create_janus_room(f"roulette:{call_id}")
        )

    async def _get_or_create_janus_room(self, redis_key, audiobridge=False):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("janus.join.missing_profile")

        async with aioredis() as redis:
            async with RedisLock(
                redis,
                key=f"januscall:lock:{redis_key}",
                timeout=90,
                wait_timeout=90,
            ):
                room_data = await redis.get(f"januscall:{redis_key}")

                if room_data:
                    # A room has been created before, check if it still exists
                    # todo: is this to slow?
                    room_data = json.loads(room_data.decode())
                    server = await database_sync_to_async(JanusServer.objects.get)(
                        url=room_data["server"]
                    )
                    try:
                        if not await videoroom_exists(server, room_data["roomId"]):
                            room_data = None
                    except JanusError as e:
                        # todo
                        raise e

                    if room_data.get("audiobridge", False) != audiobridge:
                        room_data = None

                if not room_data:
                    # no room exists
                    janus_server, turn_server = await self._servers()
                    try:
                        room_data = await create_videoroom(
                            janus_server,
                            room_id=str(uuid.uuid4()),
                            audiobridge=audiobridge,
                        )
                        await redis.setex(
                            f"januscall:{redis_key}",
                            3600 * 24,
                            json.dumps(room_data),
                        )
                    except JanusError as e:
                        if settings.SENTRY_DSN:
                            capture_exception(e)
                        await self.consumer.send_error(
                            "janus.failed", "Could not create a video session"
                        )
                else:
                    await redis.expire(
                        f"januscall:{redis}",
                        3600 * 24,
                    )
                    turn_server = await database_sync_to_async(turn.choose_server)(
                        self.consumer.world
                    )

            user_id = str(uuid.uuid4())
            await redis.setex(
                f"januscall:user:{user_id}",
                3600 * 24,
                str(self.consumer.user.pk),
            )

        room_data["sessionId"] = user_id
        if turn_server:
            room_data["iceServers"] = turn_server.get_ice_servers()
        else:
            room_data["iceServers"] = []

        await self.consumer.send_success(room_data)

    @command("identify")
    @require_world_permission(Permission.WORLD_VIEW)
    async def identify(self, body):
        async with aioredis() as redis:
            sessionid = body.get("id", "").split(";")[0]
            userid = await redis.get(f"januscall:user:{sessionid}")
            if userid:
                user = await get_public_user(
                    self.consumer.world.id,
                    userid.decode(),
                    include_admin_info=await self.consumer.world.has_permission_async(
                        user=self.consumer.user,
                        permission=Permission.WORLD_USERS_MANAGE,
                    ),
                    trait_badges_map=self.consumer.world.config.get("trait_badges_map"),
                )
                if user:
                    await self.consumer.send_success(user)
                    return
        await self.consumer.send_error(code="user.not_found")
