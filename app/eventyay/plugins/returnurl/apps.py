from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class ReturnURLApp(AppConfig):
    name = 'eventyay.plugins.returnurl'
    verbose_name = _('Redirection from order page')

    class EventyayPluginMeta:
        name = _('Redirection from order page')
        version = version
        category = 'API'
        description = _(
            'This plugin allows to link to payments and redirect back afterwards. This is useful in '
            'combination with our API.'
        )

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'eventyay.plugins.returnurl.ReturnURLApp'
