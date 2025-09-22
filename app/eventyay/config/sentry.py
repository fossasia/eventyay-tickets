import re
import weakref

from celery.exceptions import Retry
from sentry_sdk import Hub
from sentry_sdk.integrations.django import (
    DjangoIntegration,
    _before_get_response,
    _set_user_info,
)
from sentry_sdk.integrations.django.asgi import patch_get_response_async
from sentry_sdk.utils import capture_internal_exceptions


MASK = '*' * 8
KEYS = frozenset(
    [
        'password',
        'secret',
        'passwd',
        'authorization',
        'api_key',
        'apikey',
        'sentry_dsn',
        'access_token',
        'session',
    ]
)
VALUES_RE = re.compile(r'^(?:\d[ -]*?){13,16}$')


def _make_event_processor(weak_request, integration):
    def event_processor(event, hint):
        request = weak_request()
        if request is None:
            return event

        with capture_internal_exceptions():
            _set_user_info(request, event)

        return event

    return event_processor


class EventyaySentryIntegration(DjangoIntegration):
    @staticmethod
    def setup_once():
        DjangoIntegration.setup_once()
        from django.core.handlers.base import BaseHandler

        old_get_response = BaseHandler.get_response

        def sentry_patched_get_response(self, request):
            hub = Hub.current
            integration = hub.get_integration(DjangoIntegration)
            if integration is not None:
                with hub.configure_scope() as scope:
                    scope.add_event_processor(_make_event_processor(weakref.ref(request), integration))
            return old_get_response(self, request)

        BaseHandler.get_response = sentry_patched_get_response

        if hasattr(BaseHandler, 'get_response_async'):
            patch_get_response_async(BaseHandler, _before_get_response)


def ignore_retry(event, hint):
    with capture_internal_exceptions():
        if isinstance(hint['exc_info'][1], Retry):
            return None
    return event


def setup_custom_filters():
    hub = Hub.current
    with hub.configure_scope() as scope:
        scope.add_event_processor(ignore_retry)
