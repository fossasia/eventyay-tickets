from django.apps import AppConfig


class ScheduleConfig(AppConfig):
    name = 'pretalx.schedule'

    def ready(self):
        from . import signals  # noqa


default_app_config = 'pretalx.schedule.ScheduleConfig'
