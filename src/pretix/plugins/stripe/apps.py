from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from pretix import __version__ as version


class StripeApp(AppConfig):
    name = 'pretix.plugins.stripe'
    verbose_name = _("Stripe")

    class PretixPluginMeta:
        name = _("Stripe")
        author = _("the pretix team")
        version = version
        category = 'PAYMENT'
        description = _("This plugin allows you to receive credit card payments " +
                        "via Stripe")

    def ready(self):
        from . import signals, tasks

    @cached_property
    def compatibility_errors(self):
        errs = []
        try:
            import stripe  
        except ImportError:
            errs.append("Python package 'stripe' is not installed.")
        return errs
