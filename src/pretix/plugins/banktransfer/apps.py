from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from pretix import __version__ as version


class BankTransferApp(AppConfig):
    name = 'pretix.plugins.banktransfer'
    verbose_name = _("Bank transfer")

    class PretixPluginMeta:
        name = _("Bank transfer")
        author = _("the pretix team")
        category = 'PAYMENT'
        version = version
        description = _("This plugin allows you to receive payments " +
                        "via bank transfer.")

    def ready(self):
        from . import signals
        from . import tasks
        from .templatetags import commadecimal, dotdecimal  

    @cached_property
    def compatibility_warnings(self):
        errs = []
        try:
            import chardet
        except ImportError:
            errs.append(_("Install the python package 'chardet' for better CSV import capabilities."))
        return errs
