from itertools import groupby

from django.apps import apps
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

# This is also the order in which the categories are displayed.
CATEGORY_LABELS = {
    "FEATURE": pgettext_lazy("Type of plugin", "Features"),
    "INTEGRATION": pgettext_lazy("Type of plugin", "Integrations"),
    "CUSTOMIZATION": pgettext_lazy("Type of plugin", "Customizations"),
    "EXPORTER": _("Exporters"),
    "RECORDING": _("Recording integrations"),
    "LANGUAGE": _("Languages"),
    "OTHER": pgettext_lazy("Type of plugin", "Other"),
}


def get_all_plugins(event=None):
    """Return the PretalxPluginMeta classes of all plugins found in the
    installed Django apps, sorted by name. If an event is provided, only
    plugins active for that event are returned."""
    plugins = []
    for app in apps.get_app_configs():
        if getattr(app, "PretalxPluginMeta", None):
            meta = app.PretalxPluginMeta
            meta.module = app.name
            meta.app = app

            if event and hasattr(app, "is_available"):
                if not app.is_available(event):
                    continue

            plugins.append(meta)
    return sorted(
        plugins,
        key=lambda m: (
            0 if m.module.startswith("pretalx.") else 1,
            str(m.name).lower().replace("pretalx ", ""),
        ),
    )


def get_all_plugins_grouped(event=None, filter_visible=True):
    """Return a dict of all plugins found in the installed Django apps,
    grouped by category. If an event is provided, only plugins active for
    that event are returned.
    The key is a tuple of the category name and the human-readable label."""
    plugins = get_all_plugins(event)
    if filter_visible:
        plugins = [
            p
            for p in plugins
            if not p.name.startswith(".") and getattr(p, "visible", True)
        ]
    plugins_grouped = groupby(
        sorted(plugins, key=lambda p: getattr(p, "category", "OTHER")),
        lambda p: str(getattr(p, "category", "OTHER")),
    )
    # Only keep categories with at least one plugin and sort the plugins by name.
    plugins_grouped = {
        category: sorted(
            plugins, key=lambda p: str(p.name).lower().replace("pretalx ", "")
        )
        for category, plugins in plugins_grouped
        if plugins
    }

    # Now replace the category keys with the translated labels and sort the
    # categories by the order defined in CATEGORY_ORDER.
    return {
        (category, category_label): plugins_grouped[category]
        for category, category_label in CATEGORY_LABELS.items()
        if category in plugins_grouped
    }
