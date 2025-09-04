from django.apps import AppConfig


class EventConfig(AppConfig):
    name = "eventyay.event"

    def ready(self):
        from . import services  # noqa
