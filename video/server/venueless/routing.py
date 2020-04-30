from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.sessions import CookieMiddleware, SessionMiddleware

from .live import routing as live

application = ProtocolTypeRouter(
    {
        "websocket": AllowedHostsOriginValidator(
            CookieMiddleware(
                SessionMiddleware((URLRouter(live.websocket_urlpatterns)))
            ),
        ),
    }
)
