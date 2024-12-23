from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from pretix import __version__ as version


class SocialAuthApp(AppConfig):
    name = 'pretix.plugins.socialauth'
    verbose_name = _("SocialAuth")

    class PretixPluginMeta:
        name = _("SocialAuth")
        author = _("the pretix team")
        version = version
        featured = True
        description = _("This plugin allows you to login via social networks")
        visible = False


default_app_config = 'pretix.plugins.socialauth.SocialAuthApp'
