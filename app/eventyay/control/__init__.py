from django.apps import AppConfig


class ControlConfig(AppConfig):
    name = "eventyay.control"
    label = "control"

    def ready(self):
        from . import tasks  # noqa
