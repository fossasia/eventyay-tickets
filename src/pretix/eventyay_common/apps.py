from django.apps import AppConfig


class EventyayConfig(AppConfig):
    name = 'pretix.eventyay_common'


default_app_config = 'pretix.eventyay_common.EventyayConfig'
