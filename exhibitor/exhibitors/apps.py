from django.utils.translation import gettext_lazy as _

from . import __version__

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use a later version of eventyay-tickets")


class ExhibitorApp(PluginConfig):
    default = True
    name = "exhibitors"
    verbose_name = _("Exhibitors")

    class PretixPluginMeta:
        name = _("Exhibitors")
        author = "FOSSASIA"
        description = _("This plugin enables to add and control exhibitors in eventyay")
        visible = True
        featured = True
        version = __version__
        category = "FEATURE"

    def ready(self):
        from . import signals  # NOQA
