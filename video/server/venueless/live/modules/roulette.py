import json

from channels.db import database_sync_to_async
from django.conf import settings
from sentry_sdk import capture_exception

from venueless.core.permissions import Permission
from venueless.core.services import turn
from venueless.core.services.janus import JanusError, choose_server, create_room
from venueless.core.utils.redis import aioredis
from venueless.live.decorators import command, room_action
from venueless.live.exceptions import ConsumerException
from venueless.live.modules.base import BaseModule


class RouletteModule(BaseModule):
    prefix = "roulette"

    @database_sync_to_async
    def _get_blocked_users(self):
        return set(self.consumer.user.blocked_users.values_list("id", flat=True))

    async def _is_recent_pair(self, other_id):
        ids = ",".join(sorted([other_id, str(self.consumer.user.id)]))
        async with aioredis() as redis:
            redis.exists(f"roulette:pairing:{ids}")
        return ids

    async def _store_pairing(self, other_id):
        ids = ",".join(sorted([other_id, str(self.consumer.user.id)]))
        async with aioredis() as redis:
            redis.setex(f"roulette:pairing:{ids}", 3600 * 24 * 2, "paired")
        return ids

    @database_sync_to_async
    def _servers(self):
        return choose_server(self.consumer.world), turn.choose_server(
            self.consumer.world
        )

    @command("start")
    @room_action(
        permission_required=Permission.ROOM_ROULETTE_JOIN,
        module_required="networking.roulette",
    )
    async def start(self, body):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("roulette.start.missing_profile")

        blocked_users = await self._get_blocked_users()

        listkey = f"roulette:waiting:{self.room.id}"
        seen = set()
        janus_room_info = None
        async with aioredis() as redis:
            while True:
                raw_janus_room_info = await redis.lpop(listkey)
                if not raw_janus_room_info:  # no rooms available
                    break
                janus_room_info = json.loads(raw_janus_room_info)

                full_loop_detected = janus_room_info["roomId"] in seen
                seen.add(janus_room_info["roomId"])

                skip_this = (
                    full_loop_detected
                    or janus_room_info["creating_user"] in blocked_users
                    or await self._is_recent_pair(janus_room_info["creating_user"])
                )
                if skip_this:
                    await redis.rpush(
                        listkey, raw_janus_room_info
                    )  # put back on the queue
                    janus_room_info = None
                    if full_loop_detected:
                        break
                    else:
                        continue
                else:
                    # this is it!
                    break

        # todo: there's a race condition here, if a second person hits start while the first person's room is still
        # being created on the janus server, they will be in separate rooms, which is bad if no more people join.
        # can we fully solve this without some locking that would be bad for scalability?

        if not janus_room_info:  # no room found, create a new one
            janus_server, turn_server = await self._servers()
            if not janus_server:
                await self.consumer.send_error(
                    "roulette.no_server", "No server available"
                )
                return
            try:
                janus_room_info = await create_room(janus_server)
            except JanusError as e:
                if settings.SENTRY_DSN:
                    capture_exception(e)
                await self.consumer.send_error(
                    "roulette.failed", "Could not create a video session"
                )

            janus_room_info["creating_user"] = str(self.consumer.user.pk)
            await redis.rpush(listkey, json.dumps(janus_room_info))
        else:  # existing room, store pairing
            turn_server = await database_sync_to_async(turn.choose_server)(
                self.consumer.world
            )
            await self._store_pairing(janus_room_info["creating_user"])

        if turn_server:
            janus_room_info["iceServers"] = turn_server.get_ice_servers()
        else:
            janus_room_info["iceServers"] = []
        await self.consumer.send_success(janus_room_info)
