from channels.generic.websocket import AsyncJsonWebsocketConsumer

from ..core.services.event import get_event_config
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

        await self.send_json(["event.config", event_config])

    async def disconnect(self, close_code):
        pass

    # Receive message from WebSocket
    async def receive_json(self, content, **kargs):
        if content[0] == "ping":
            await self.send_json(["pong", content[1]])
        elif content[0].startswith("chat."):
            await ChatModule().dispatch_command(self, content)

    async def dispatch(self, message):
        if message["type"].startswith("chat."):
            await ChatModule().dispatch_event(self, message)
        else:
            await super().dispatch(message)
