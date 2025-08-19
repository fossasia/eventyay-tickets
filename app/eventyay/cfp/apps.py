from django.apps import AppConfig


class CfPConfig(AppConfig):
    name = 'eventyay.cfp'

    def ready(self):
        from .phrases import CfPPhrases  # noqa
