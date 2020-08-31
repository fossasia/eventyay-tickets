from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from .live import routing as live

application = ProtocolTypeRouter(
    {
        "websocket": AllowedHostsOriginValidator(URLRouter(live.websocket_urlpatterns)),
    }
)


class PatchedSentryAsgiMiddleware(SentryAsgiMiddleware):
    # Workaround for https://github.com/getsentry/sentry-python/issues/700

    def event_processor(self, event, hint, asgi_scope):
        asgi_scope.setdefault("method", "WEBSOCKET")
        return super().event_processor(event, hint, asgi_scope)


if settings.SENTRY_DSN:
    application = PatchedSentryAsgiMiddleware(application)
