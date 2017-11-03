from django.apps import AppConfig


class OrgaConfig(AppConfig):
    name = 'pretalx.orga'

    def ready(self):
        from .phrases import OrgaPhrases  # noqa
