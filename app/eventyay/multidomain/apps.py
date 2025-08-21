from django.apps import AppConfig


class EventyayMultidomainConfig(AppConfig):
    name = 'eventyay.multidomain'
    label = 'multidomain'


default_app_config = 'eventyay.multidomain.EventyayMultidomainConfig'
