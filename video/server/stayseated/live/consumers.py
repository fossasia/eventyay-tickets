from channels.generic.websocket import AsyncJsonWebsocketConsumer

from ..core.services.event import get_event_config
from .modules.auth import AuthModule
from .modules.chat import ChatModule


class MainConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        event_config = await get_event_config(
            self.scope["url_route"]["kwargs"]["event"]
        )
        if event_config is None:
            await self.send_json(["error", None, "unknown event"], close=True)
            return

    async def disconnect(self, close_code):
        pass

    # Receive message from WebSocket
    async def receive_json(self, content, **kargs):
        self.content = content
        if content[0] == "ping":
            await self.send_json(["pong", content[1]])
        if not "user" in self.scope and not "user_id" in self.scope.get("session", {}):
            if self.content[0] == "authenticate":
                await AuthModule().dispatch_command(self, content)
            else:
                await self.send_error("protocol.unauthenticated")
        else:
            if content[0].startswith("chat."):
                await ChatModule().dispatch_command(self, content)
            elif content[0].startswith("user."):
                await AuthModule().dispatch_command(self, content)

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

    async def send_error(self, code, message=None):
        data = {"code": code}
        if message:
            data["message"] = message
        await self.send_json(self.build_response("error", data))

    async def send_success(self, data=None):
        await self.send_json(self.build_response("success", data))
