from django.apps import AppConfig


class CfPConfig(AppConfig):
    name = 'pretalx.cfp'

    def ready(self):
        from . import permissions  # noqa
        from .phrases import CfPPhrases  # noqa


default_app_config = 'pretalx.cfp.CfPConfig'
