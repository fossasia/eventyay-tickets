from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from pretix import __version__ as version


class PaypalApp(AppConfig):
    name = 'pretix.plugins.paypal'
    verbose_name = _("PayPal")

    class PretixPluginMeta:
        name = _("PayPal")
        author = _("")
        version = version
        category = 'PAYMENT'
        featured = True
        picture = 'plugins/paypal/paypal_logo.svg'
        description = _("This plugin allows you to receive payments via PayPal")

    def ready(self):
        from . import signals  # NOQA
