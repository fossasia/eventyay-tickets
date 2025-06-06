from django.apps import AppConfig

class EventyayBaseConfig(AppConfig):
    name = 'eventyay.base'
    label = 'eventyaybase'

    def ready(self):
        pass


default_app_config = 'eventyay.base.EventyayBaseConfig'
