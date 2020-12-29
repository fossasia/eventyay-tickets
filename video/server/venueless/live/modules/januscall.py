import json

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
    create_room,
    room_exists,
)
from venueless.core.utils.redis import aioredis
from venueless.live.decorators import command, room_action
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
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("janus.join.missing_profile")

        async with aioredis() as redis:
            async with RedisLock(
                redis, key=f"januscall:lock:{self.room.id}", timeout=90, wait_timeout=90
            ):
                room_data = await redis.get(f"januscall:room:{self.room.id}")

                if room_data:
                    # A room has been created before, check if it still exists
                    # todo: is this to slow?
                    room_data = json.loads(room_data.decode())
                    server = await database_sync_to_async(JanusServer.objects.get)(
                        url=room_data["server"]
                    )
                    try:
                        if not await room_exists(server, room_data["roomId"]):
                            room_data = None
                    except JanusError as e:
                        # todo
                        raise e

                if not room_data:
                    # no room exists
                    janus_server, turn_server = await self._servers()
                    try:
                        room_data = await create_room(janus_server)
                        await redis.set(
                            f"januscall:room:{self.room.id}", json.dumps(room_data)
                        )
                    except JanusError as e:
                        if settings.SENTRY_DSN:
                            capture_exception(e)
                        await self.consumer.send_error(
                            "roulette.failed", "Could not create a video session"
                        )
                else:
                    turn_server = await database_sync_to_async(turn.choose_server)(
                        self.consumer.world
                    )

        if turn_server:
            room_data["iceServers"] = turn_server.get_ice_servers()
        else:
            room_data["iceServers"] = []
        await self.consumer.send_success(room_data)
