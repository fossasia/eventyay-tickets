import asyncio
import logging
import random
import time
import uuid

import orjson
from channels.exceptions import StopConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.db import OperationalError
from sentry_sdk import capture_exception, configure_scope
from websockets import ConnectionClosed, ConnectionClosedError

from venueless.core.services.connections import (
    ping_connection,
    register_connection,
    unregister_connection,
)
from venueless.core.services.world import get_world
from venueless.live.exceptions import ConsumerException

from ..core.utils.redis import aioredis
from ..core.utils.statsd import statsd
from .channels import GROUP_VERSION
from .modules.announcement import AnnouncementModule
from .modules.auth import AuthModule
from .modules.bbb import BBBModule
from .modules.chat import ChatModule
from .modules.exhibition import ExhibitionModule
from .modules.januscall import JanusCallModule
from .modules.poll import PollModule
from .modules.poster import PosterModule
from .modules.question import QuestionModule
from .modules.room import RoomModule
from .modules.roulette import RouletteModule
from .modules.world import WorldModule
from .modules.zoom import ZoomModule

logger = logging.getLogger(__name__)


class MainConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.socket_id = str(uuid.uuid4())
        self.world = None
        self.room_cache = {}
        self.channel_cache = {}
        self.components = {}
        self.conn_time = 0
        self.last_conn_ping = 0

        # known_room_id_cache: contain IDs of rooms we know this user is allowed to see. updated after login and with
        # world update. used to quickly filter events.
        self.known_room_id_cache = set()

    async def connect(self):
        self.content = []
        self.conn_time = time.time()
        world_id = self.scope["url_route"]["kwargs"]["world"]
        await self.accept()
        if settings.REDIS_USE_PUBSUB:
            async with aioredis() as redis:
                await redis.zadd(
                    f"version.{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
                    int(time.time()),
                    self.channel_name,
                )
                await redis.expire(
                    f"version.{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
                    24 * 3600,
                )
        else:
            await self.channel_layer.group_add(
                GROUP_VERSION.format(
                    label=settings.VENUELESS_COMMIT
                    + "."
                    + settings.VENUELESS_ENVIRONMENT
                ),
                self.channel_name,
            )

        await register_connection()

        try:
            self.world = await get_world(world_id)
        except OperationalError:
            # We use connection pooling, so if the database server went away since the last connection
            # terminated, Django won't know and we'll get an OperationalError. We just silently re-try
            # once, since Django will then use a new connection.
            self.world = await get_world(world_id)

        if self.world is None:
            await self.send_error("world.unknown_world", close=True)
            return

        if settings.SENTRY_DSN:
            with configure_scope() as scope:
                scope.set_extra("world", self.world.id)

        async with statsd() as s:
            s.increment(f"connection.established,world={world_id}")

        self.components = {
            "announcement": AnnouncementModule(self),
            "chat": ChatModule(self),
            "bbb": BBBModule(self),
            "zoom": ZoomModule(self),
            "januscall": JanusCallModule(self),
            "exhibition": ExhibitionModule(self),
            "poster": PosterModule(self),
            "question": QuestionModule(self),
            "poll": PollModule(self),
            "room": RoomModule(self),
            "roulette": RouletteModule(self),
            "user": AuthModule(self),
            "world": WorldModule(self),
        }

    async def disconnect(self, close_code):
        for c in self.components.values():
            if hasattr(c, "dispatch_disconnect"):
                await c.dispatch_disconnect(close_code)

        if settings.REDIS_USE_PUBSUB:
            async with aioredis() as redis:
                await redis.zrem(
                    f"version.{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
                    self.channel_name,
                )
        else:
            await self.channel_layer.group_discard(
                GROUP_VERSION.format(
                    label=settings.VENUELESS_COMMIT
                    + "."
                    + settings.VENUELESS_ENVIRONMENT
                ),
                self.channel_name,
            )

        await unregister_connection()

    # Receive message from WebSocket
    async def receive_json(self, content, **kargs):
        self.content = content

        if content[0] == "ping":
            await self.send_json(["pong", content[1]])
            self.last_conn_ping = await ping_connection(self.last_conn_ping, self.user)
            return

        if not self.user:
            if content[0] == "authenticate":
                await self.world.refresh_from_db_if_outdated(allowed_age=30)
                await self.components["user"].login(content[-1])
            else:
                await self.send_error("protocol.unauthenticated")
            return

        async with statsd() as s:
            s.increment(f"command.received,command={content[0]},world={self.world.pk}")

        namespace = content[0].split(".")[0]
        component = self.components.get(namespace)
        if component:
            try:
                await self.world.refresh_from_db_if_outdated(allowed_age=900)
                await self.user.refresh_from_db_if_outdated(allowed_age=30)
                await component.dispatch_command(content)
            except ConsumerException as e:
                await self.send_error(e.code, e.message)
        else:
            await self.send_error("protocol.unknown_command")

    async def dispatch(self, message):
        if self.conn_time and time.time() - self.conn_time > 3600 * 24 * random.uniform(
            0.9, 1
        ):
            # Django channels forgets which groups we're in after `group_expiry`, usually a day, so we do a force
            # reconnect every day. That's good for memory usage on both ends as well, probably :) We randomize the
            # interval a little to prevent everyone reconnecting at the same time.
            return await self.close()

        try:
            async with statsd() as s:
                s.increment(
                    f"event.received,type={message['type']},world={self.world.pk if self.world else 'None'}"
                )

            if message["type"] == "connection.drop":
                return await self.close()
            elif message["type"] == "connection.reload":
                await self.send_json(["connection.reload", {}])
                await asyncio.sleep(2)
                await self.close()
                return
            elif message["type"] == "connection.replaced":
                await self.send_error(
                    code="connection.replaced", message="Connection replaced"
                )
                await asyncio.sleep(0.5)
                await self.close()
                return
            elif message["type"] == "user.broadcast":
                if self.socket_id != message["socket"]:
                    await self.user.refresh_from_db_if_outdated(allowed_age=0)
                    await self.send_json([message["event_type"], message["data"]])
                return

            namespace = message["type"].split(".")[0]
            component = self.components.get(namespace)
            if component:
                if hasattr(component, "dispatch_event"):
                    return await component.dispatch_event(message)
            else:
                return await super().dispatch(message)
        except ConnectionClosed:  # pragma: no cover
            # Connection vanished while we were trying to send something, oops. Nothing we can do except hope our
            # disconnect handler will be called.
            pass
        except Exception as e:
            if isinstance(e, StopConsumer):
                raise e
            if settings.SENTRY_DSN:
                capture_exception(e)
            logger.exception("Encountered exception, close socket.")
            self.content = []
            await self.send_error(code="server.fatal", message="Fatal Server Error")
            await asyncio.sleep(0.5)
            await self.close()
            async with statsd() as s:
                s.increment(
                    f"error.fatal,world={self.world.pk if self.world else 'None'}"
                )

    def build_response(self, status, data):
        if data is None:
            data = {}
        response = [status]
        if len(self.content) == 3:
            response.append(self.content[1])
        response.append(data)
        return response

    async def send_error(self, code, message=None, close=False, details=None):
        data = {"code": code}
        if message:
            data["message"] = message
        if details:
            data["details"] = details
        await self.send_json(self.build_response("error", data), close=close)

    async def send_success(self, data=None, close=False):
        await self.send_json(self.build_response("success", data), close=close)

    # Override send and receive methods to use orjson and less function calls

    async def send_json(self, content, close=False):
        try:
            await super().send(text_data=orjson.dumps(content).decode(), close=close)
        except (RuntimeError, ConnectionClosedError):
            # socket has been closed in the meantime
            pass

    @classmethod
    async def decode_json(cls, text_data):
        return orjson.loads(text_data)
