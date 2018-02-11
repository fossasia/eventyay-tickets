from django.apps import AppConfig


class OrgaConfig(AppConfig):
    name = 'pretalx.orga'

    def ready(self):
        from . import permissions  # noqa
        from .phrases import OrgaPhrases  # noqa
        from . import signals  # noqa


default_app_config = 'pretalx.orga.OrgaConfig'
