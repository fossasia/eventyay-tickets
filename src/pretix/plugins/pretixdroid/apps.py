from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from pretix import __version__ as version


class PretixdroidApp(AppConfig):
    name = 'pretix.plugins.pretixdroid'
    verbose_name = _("Old check-in device API")

    class PretixPluginMeta:
        name = _("Old check-in device API")
        author = _("the pretix team")
        version = version
        visible = False
        restricted = True
        category = 'INTEGRATION'
        description = _("This plugin allows you to use the pretixdroid and pretixdesk apps for your event.")


default_app_config = 'pretix.plugins.pretixdroid.PretixdroidApp'
