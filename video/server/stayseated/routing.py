from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

from .live import routing as live

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter(
            live.websocket_urlpatterns
        )
    ),
})
