from django.apps import AppConfig


class ScheduleConfig(AppConfig):
    name = 'eventyay.schedule'

    def ready(self):
        from . import signals  # noqa
        from .phrases import SchedulePhrases  # noqa
