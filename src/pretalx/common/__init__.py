from contextlib import suppress

from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = 'pretalx.common'

    def ready(self):
        from . import signals  # noqa


with suppress(ImportError):
    import pretalx.celery_app as celery  # NOQA

default_app_config = 'pretalx.common.CommonConfig'
