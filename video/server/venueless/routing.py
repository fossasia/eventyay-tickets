from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from .live import routing as live

application = ProtocolTypeRouter(
    {"websocket": AllowedHostsOriginValidator(URLRouter(live.websocket_urlpatterns)),}
)
