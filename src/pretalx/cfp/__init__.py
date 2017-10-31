from django.apps import AppConfig


class CfPConfig(AppConfig):
    name = 'pretalx.cfp'

    def ready(self):
        from .phrases import CfPPhrases  # noqa
