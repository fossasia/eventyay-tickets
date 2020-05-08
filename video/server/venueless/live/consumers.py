import uuid

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from venueless.core.services.world import get_world
from venueless.live.exceptions import ConsumerException

from .modules.auth import AuthModule
from .modules.bbb import BBBModule
from .modules.chat import ChatModule


class MainConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.content = {}
        self.components = {
            "chat": ChatModule(),
            "user": AuthModule(),
            "bbb": BBBModule(),
        }
        self.user = None
        self.socket_id = str(uuid.uuid4())
        await self.accept()
        world = await get_world(self.scope["url_route"]["kwargs"]["world"])
        if world is None:
            await self.send_error("world.unknown_world", close=True)
            return

    async def disconnect(self, close_code):
        for c in self.components.values():
            if hasattr(c, "dispatch_disconnect"):
                await c.dispatch_disconnect(self, close_code)

    async def user_broadcast(self, event_type, data):
        """
        Broadcast a message to other clients of the same user.
        """
        await self.channel_layer.group_send(
            f"user.{self.user['id']}",
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
        if message["type"] == "user.broadcast":
            if self.socket_id != message["socket"]:
                await self.send_json([message["event_type"], message["data"]])
        elif message["type"] == "world.update":
            await self.components["user"].dispatch_event(self, message)
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
