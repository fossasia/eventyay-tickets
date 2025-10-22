from django.utils.translation import gettext_lazy

from . import __version__

# Try Eventyay plugin base first, then fall back to Eventyay again (no pretix usage here)
try:  # Eventyay fork environment
    from eventyay.base.plugins import PluginConfig as _BasePluginConfig  # type: ignore
except Exception:  # pragma: no cover - environment mismatch
    from eventyay.base.plugins import PluginConfig as _BasePluginConfig  # Fallback to eventyay


class PluginApp(_BasePluginConfig):
    default = True
    name = 'pretix_venueless'
    verbose_name = 'Eventyay Video'

    class PretixPluginMeta:  # Keep for upstream pretix compatibility
        name = gettext_lazy('Eventyay Video')
        author = 'Eventyay'
        description = gettext_lazy('Grant access to your eventyay video event to your customers.')
        visible = True
        picture = "pretix_venueless/eventyay-logo.192.png"
        featured = True
        version = __version__
        category = 'INTEGRATION'

    class EventyayPluginMeta:  # For Eventyay compatibility
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
