from django.apps import AppConfig


class ControlConfig(AppConfig):
    name = "venueless.control"
    label = "control"

    def ready(self):
        from . import tasks  # noqa
