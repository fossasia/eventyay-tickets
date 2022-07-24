from django.apps import AppConfig
from django.utils.translation import gettext_lazy


class PluginApp(AppConfig):
    name = "pretalx_venueless"
    verbose_name = "Venueless integration"

    class PretalxPluginMeta:
        name = gettext_lazy("Venueless integration")
        author = "Tobias Kunze"
        description = gettext_lazy(
            "Venueless integration in pretalx: Notify venueless about new schedule releases!"
        )
        visible = True
        version = "1.2.0"

    def ready(self):
        from . import signals  # NOQA
