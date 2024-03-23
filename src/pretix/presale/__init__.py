from django.apps import AppConfig


class PretixPresaleConfig(AppConfig):
    name = 'pretix.presale'
    label = 'pretixpresale'

    def ready(self):
        from . import style  # noqa


