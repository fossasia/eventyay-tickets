from django.apps import AppConfig


class EventConfig(AppConfig):
    name = 'pretalx.event'

    def ready(self):
        from . import services  # noqa


default_app_config = 'pretalx.event.EventConfig'
