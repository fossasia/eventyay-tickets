from channels.generic.websocket import AsyncJsonWebsocketConsumer

from stayseated.live.exceptions import ConsumerException

from ..core.services.world import get_world_config
from .modules.auth import AuthModule
from .modules.chat import ChatModule


class MainConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.content = {}
        await self.accept()
        world_config = await get_world_config(
            self.scope["url_route"]["kwargs"]["world"]
        )
        if world_config is None:
            await self.send_error("world.unknown_world", close=True)
            return

    async def disconnect(self, close_code):
        pass

    @property
    def user(self):
        return self.scope.get("session", {}).get("user", {})

    @user.setter
    def user(self, value):
        self.scope["session"]["user"] = value

    # Receive message from WebSocket
    async def receive_json(self, content, **kargs):
        self.content = content
        if content[0] == "ping":
            await self.send_json(["pong", content[1]])
            return
        if "user" not in self.scope and "user" not in self.scope.get("session", {}):
            if self.content[0] == "authenticate":
                await AuthModule().dispatch_command(self, content)
            else:
                await self.send_error("protocol.unauthenticated")
            return
        components = {"chat": ChatModule, "user": AuthModule}
        namespace = content[0].split(".")[0]
        component = components.get(namespace)
        if component:
            try:
                await component().dispatch_command(self, content)
            except ConsumerException as e:
                await self.send_error(e.code, e.message)
        else:
            await self.send_error("protocol.unknown_command")

    async def dispatch(self, message):
        if message["type"].startswith("chat."):
            await ChatModule().dispatch_event(self, message)
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
