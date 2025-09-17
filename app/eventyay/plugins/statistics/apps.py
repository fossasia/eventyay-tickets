from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class StatisticsApp(AppConfig):
    name = 'eventyay.plugins.statistics'
    verbose_name = _('Statistics')

    class EventyayPluginMeta:
        name = _('Statistics')
        version = version
        category = 'FEATURE'
        description = _('This plugin shows you various statistics.')

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'eventyay.plugins.statistics.StatisticsApp'
