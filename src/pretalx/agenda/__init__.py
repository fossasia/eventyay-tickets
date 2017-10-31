from django.apps import AppConfig


class AgendaConfig(AppConfig):
    name = 'pretalx.agenda'

    def ready(self):
        from .messages import AgendaMessages  # noqa
