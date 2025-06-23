from contextlib import suppress

from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "pretalx.common"

    def ready(self):
        from . import log_display  # noqa
        from . import signals  # noqa
        from . import update_check  # noqa


with suppress(ImportError):
    from pretalx import celery_app as celery  # NOQA
