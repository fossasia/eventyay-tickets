from django.apps import AppConfig


class EventyayControlConfig(AppConfig):
    name = 'eventyay.control'
    label = 'eventyaycontrol'

    def ready(self):
        from .views import dashboards  # noqa
        from . import logdisplay  # noqa


default_app_config = 'eventyay.control.EventyayControlConfig'
