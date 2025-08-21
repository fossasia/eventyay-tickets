from django.apps import AppConfig


class EventyayPresaleConfig(AppConfig):
    name = 'eventyay.presale'
    label = 'presale'

    def ready(self):
        from . import style  # noqa


default_app_config = 'eventyay.presale.EventyayPresaleConfig'
