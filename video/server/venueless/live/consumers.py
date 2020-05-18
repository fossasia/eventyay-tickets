import json
import uuid

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from venueless.core.services.connections import (
    ping_connection,
    register_connection,
    unregister_connection,
)
from venueless.core.services.world import get_world
from venueless.live.channels import GROUP_USER, GROUP_VERSION
from venueless.live.exceptions import ConsumerException

from ..core.utils.json import CustomJSONEncoder
from .modules.auth import AuthModule
from .modules.bbb import BBBModule
from .modules.chat import ChatModule
from .modules.world import WorldModule


class MainConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.content = {}
        self.components = {
            "chat": ChatModule(),
            "user": AuthModule(),
            "bbb": BBBModule(),
            "room": WorldModule(),
            "world": WorldModule(),
        }
        self.user = None
        self.socket_id = str(uuid.uuid4())

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

    async def disconnect(self, close_code):
        for c in self.components.values():
            if hasattr(c, "dispatch_disconnect"):
                await c.dispatch_disconnect(self, close_code)

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
            if self.content[0] == "authenticate":
                await self.components["user"].dispatch_command(self, content)
            else:
                await self.send_error("protocol.unauthenticated")
            return
        namespace = content[0].split(".")[0]
        component = self.components.get(namespace)
        if component:
            try:
                await component.dispatch_command(self, content)
            except ConsumerException as e:
                await self.send_error(e.code, e.message)
        else:
            await self.send_error("protocol.unknown_command")

    async def dispatch(self, message):
        if message["type"] == "connection.drop":
            await self.close()
        elif message["type"] == "connection.reload":
            await self.send_json(["connection.reload", {}])
        elif message["type"] == "user.broadcast":
            if self.socket_id != message["socket"]:
                await self.components["user"].reload_user()
                await self.send_json([message["event_type"], message["data"]])
        elif message["type"] in ("world.update", "room.create"):  # broadcast types
            await self.components["world"].dispatch_event(self, message)
        elif message["type"].startswith("chat."):
            await self.components["chat"].dispatch_event(self, message)
        else:
            await super().dispatch(message)

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

    @classmethod
    async def encode_json(cls, content):
        return json.dumps(content, cls=CustomJSONEncoder)
