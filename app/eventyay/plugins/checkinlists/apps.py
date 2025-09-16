from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class CheckinlistsApp(AppConfig):
    name = 'eventyay.plugins.checkinlists'
    verbose_name = _('Check-in lists')

    class EventyayPluginMeta:
        name = _('Check-in list exporter')
        version = version
        visible = False
        description = _('This plugin allows you to generate check-in lists for your conference.')

    def ready(self):
        from . import signals  # NOQA

    @cached_property
    def compatibility_errors(self):
        errs = []
        try:
            import reportlab  # NOQA
        except ImportError:
            errs.append("Python package 'reportlab' is not installed.")
        return errs


default_app_config = 'eventyay.plugins.checkinlists.CheckinlistsApp'
