from django.apps import AppConfig


class AgendaConfig(AppConfig):
    name = 'pretalx.agenda'

    def ready(self):
        from . import permissions  # noqa
        from .phrases import AgendaPhrases  # noqa
