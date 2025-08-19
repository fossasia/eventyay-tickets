from django.apps import AppConfig


class EventyayApiConfig(AppConfig):
    name = 'eventyay.api'

    def ready(self):
        from . import signals, webhooks  # noqa


default_app_config = 'eventyay.api.EventyayApiConfig'
