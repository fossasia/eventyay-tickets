from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class ManualPaymentApp(AppConfig):
    name = 'eventyay.plugins.manualpayment'
    verbose_name = _('Manual payment')

    class EventyayPluginMeta:
        name = _('Manual payment')
        version = version
        category = 'PAYMENT'
        description = _('This plugin adds a customizable payment method for manual processing.')


default_app_config = 'eventyay.plugins.manualpayment.ManualPaymentApp'
