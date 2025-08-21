from django.apps import AppConfig


class EventyayHelpersConfig(AppConfig):
    name = 'eventyay.helpers'
    label = 'helpers'


default_app_config = 'eventyay.helpers.EventyayHelpersConfig'
