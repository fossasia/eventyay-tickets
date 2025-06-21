from contextlib import suppress

from django.apps import AppConfig


class AgendaConfig(AppConfig):
    name = "pretalx.agenda"

    def ready(self):
        from . import permissions  # noqa
        from .phrases import AgendaPhrases  # noqa


with suppress(ImportError):
    from pretalx import celery_app as celery  # noqa
