from django.apps import AppConfig


class ControlConfig(AppConfig):
    name = "eventyay.base.video-control"
    label = "control"

    def ready(self):
        from . import tasks  # noqa
