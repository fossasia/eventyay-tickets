from django.apps import AppConfig


class OrgaConfig(AppConfig):
    name = "eventyay.orga"

    def ready(self):
        from . import permissions  # noqa
        from . import receivers  # noqa
        from . import signals  # noqa
        from .phrases import OrgaPhrases  # noqa
