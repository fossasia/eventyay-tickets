from contextlib import suppress

from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "eventyay.common"

    def ready(self):
        from . import checks  # noqa
        from . import log_display  # noqa
        from . import signals  # noqa
        # from . import update_check  # noqa


with suppress(ImportError):
    from eventyay import celery_app as celery  # NOQA
