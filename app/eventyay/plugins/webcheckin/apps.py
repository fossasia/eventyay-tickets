from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class WebCheckinApp(AppConfig):
    name = 'eventyay.plugins.webcheckin'
    verbose_name = _('Web-based check-in')

    class EventyayPluginMeta:
        name = _('Web-based check-in')
        version = version
        category = 'FEATURE'
        featured = True
        description = _('This plugin allows you to perform check-in actions in your browser.')

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'eventyay.plugins.webcheckin.WebCheckinApp'
