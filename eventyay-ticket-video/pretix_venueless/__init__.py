from django.utils.translation import gettext_lazy

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2.7 or above to run this plugin!")

__version__ = '1.1.0'


class PluginApp(PluginConfig):
    name = 'pretix_venueless'
    verbose_name = 'Venueless'

    class PretixPluginMeta:
        name = gettext_lazy('Venueless')
        author = 'Raphael Michel'
        description = gettext_lazy('Grant access to your venueless event to your customers')
        visible = True
        picture = "pretix_venueless/logo.svg"
        featured = True
        version = __version__
        category = 'INTEGRATION'
        compatibility = "pretix>=3.8.0"

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'pretix_venueless.PluginApp'
