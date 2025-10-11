from django.utils.translation import gettext_lazy

from . import __version__

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2.7 or above to run this plugin!")


class PluginApp(PluginConfig):
    default = True
    name = 'pretix_venueless'
    verbose_name = 'Eventyay Video'

    class PretixPluginMeta:
        name = gettext_lazy('Eventyay Video')
        author = 'Eventyay'
        description = gettext_lazy('Grant access to your eventyay video event to your customers.')
        visible = True
        picture = "pretix_venueless/eventyay-logo.192.png"
        featured = True
        version = __version__
        category = 'INTEGRATION'

    def ready(self):
        from . import signals  # NOQA
