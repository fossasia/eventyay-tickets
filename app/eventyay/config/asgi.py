"""
ASGI config for Eventyay project.

This is the main ASGI application entry point. Daphne and other ASGI servers
should load this file (eventyay.config.asgi:application).

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')

# Initialize Django ASGI application early to ensure apps are loaded
import django
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

# Now import modules that depend on Django apps
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from eventyay.features.live import routing as live

# Configure ASGI application with WebSocket and HTTP support
application = ProtocolTypeRouter(
    {
        'websocket': AllowedHostsOriginValidator(URLRouter(live.websocket_urlpatterns)),
        'http': django_asgi_app,
    }
)


class PatchedSentryAsgiMiddleware(SentryAsgiMiddleware):
    """
    Workaround for https://github.com/getsentry/sentry-python/issues/700
    """

    def event_processor(self, event, hint, asgi_scope):
        asgi_scope.setdefault('method', 'WEBSOCKET')
        return super().event_processor(event, hint, asgi_scope)


# Wrap with Sentry middleware if configured
if settings.SENTRY_DSN:
    application = PatchedSentryAsgiMiddleware(application)
