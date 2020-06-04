import asyncio
import logging
import random
import time
import uuid

import orjson
from channels.exceptions import StopConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from sentry_sdk import capture_exception, configure_scope
from websockets import ConnectionClosed

from venueless.core.services.connections import (
    ping_connection,
    register_connection,
    unregister_connection,
)
from venueless.core.services.world import get_world
from venueless.live.channels import GROUP_USER, GROUP_VERSION
from venueless.live.exceptions import ConsumerException

from .modules.auth import AuthModule
from .modules.bbb import BBBModule
from .modules.chat import ChatModule
from .modules.room import RoomModule
from .modules.world import WorldModule

logger = logging.getLogger(__name__)


class MainConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.socket_id = str(uuid.uuid4())
        self.world = None
        self.room_cache = {}
        self.components = {}
        self.conn_time = 0

    async def connect(self):
        self.content = []
        self.conn_time = time.time()
        await self.accept()
        await self.channel_layer.group_add(
            GROUP_VERSION.format(
                label=settings.VENUELESS_COMMIT + "." + settings.VENUELESS_ENVIRONMENT
            ),
            self.channel_name,
        )
        await register_connection()

        self.world = await get_world(self.scope["url_route"]["kwargs"]["world"])
        if self.world is None:
            await self.send_error("world.unknown_world", close=True)
            return

        if settings.SENTRY_DSN:
            with configure_scope() as scope:
                scope.set_extra("world", self.world.id)

        self.components = {
            "chat": ChatModule(self),
            "user": AuthModule(self),
            "bbb": BBBModule(self),
            "room": RoomModule(self),
            "world": WorldModule(self),
        }

    async def disconnect(self, close_code):
        for c in self.components.values():
            if hasattr(c, "dispatch_disconnect"):
                await c.dispatch_disconnect(close_code)

        await self.channel_layer.group_discard(
            GROUP_VERSION.format(
                label=settings.VENUELESS_COMMIT + "." + settings.VENUELESS_ENVIRONMENT
            ),
            self.channel_name,
        )
        await unregister_connection()

    async def user_broadcast(self, event_type, data):
        """
        Broadcast a message to other clients of the same user.
        """
        await self.channel_layer.group_send(
            GROUP_USER.format(id=self.user.id),
            {
                "type": "user.broadcast",
                "event_type": event_type,
                "data": data,
                "socket": self.socket_id,
            },
        )

    # Receive message from WebSocket
    async def receive_json(self, content, **kargs):
        self.content = content

        if content[0] == "ping":
            await self.send_json(["pong", content[1]])
            await ping_connection()
            return

        if not self.user:
            if content[0] == "authenticate":
                await self.world.refresh_from_db_if_outdated()
                await self.components["user"].login(content[-1])
            else:
                await self.send_error("protocol.unauthenticated")
            return

        namespace = content[0].split(".")[0]
        component = self.components.get(namespace)
        if component:
            try:
                await self.world.refresh_from_db_if_outdated()
                await self.user.refresh_from_db_if_outdated()
                await component.dispatch_command(content)
            except ConsumerException as e:
                await self.send_error(e.code, e.message)
        else:
            await self.send_error("protocol.unknown_command")

    async def dispatch(self, message):
        if self.conn_time and time.time() - self.conn_time > self.channel_layer.group_expiry * random.uniform(
            0.9, 1
        ):
            # Django channels forgets which groups we're in after `group_expiry`, usually a day, so we do a force
            # reconnect every day. That's good for memory usage on both ends as well, probably :) We randomize the
            # interval a little to prevent everying reconnecting at the same time.
            return await self.close()

        try:
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
                    await self.user.refresh_from_db_if_outdated()
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

    def build_response(self, status, data):
        if data is None:
            data = {}
        response = [status]
        if len(self.content) == 3:
            response.append(self.content[1])
        response.append(data)
        return response

    async def send_error(self, code, message=None, close=False):
        data = {"code": code}
        if message:
            data["message"] = message
        await self.send_json(self.build_response("error", data), close=close)

    async def send_success(self, data=None, close=False):
        await self.send_json(self.build_response("success", data), close=close)

    # Override send and receive methods to use orjson and less function calls

    async def send_json(self, content, close=False):
        await super().send(text_data=orjson.dumps(content).decode(), close=close)

    @classmethod
    async def decode_json(cls, text_data):
        return orjson.loads(text_data)
