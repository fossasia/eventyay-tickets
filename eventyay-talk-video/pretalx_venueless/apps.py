from django.apps import AppConfig
from django.utils.translation import gettext_lazy

from . import __version__


class PluginApp(AppConfig):
    name = "pretalx_venueless"
    verbose_name = "Eventyay video integration"

    class PretalxPluginMeta:
        name = gettext_lazy("Eventyay video integration")
        author = "Eventyay"
        description = gettext_lazy(
            "Eventyay video integration in pretalx: Notify eventyay about new schedule releases!"
        )
        visible = True
        version = __version__
        category = "INTEGRATION"

    def ready(self):
        from . import signals  # NOQA
