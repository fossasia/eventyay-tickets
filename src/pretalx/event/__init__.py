from django.apps import AppConfig


class EventConfig(AppConfig):
    name = 'pretalx.event'

    def ready(self):
        from . import services  # noqa
