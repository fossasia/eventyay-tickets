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
    plugins available for that event are returned."""
    plugins = []
    for app in apps.get_app_configs():
        if getattr(app, "PretalxPluginMeta", None):
            meta = app.PretalxPluginMeta
            meta.module = app.name
            meta.app = app

            if event and hasattr(app, "is_available") and not app.is_available(event):
                continue

            plugins.append(meta)
    return sorted(
        plugins,
        key=lambda module: (
            0 if module.module.startswith("pretalx.") else 1,
            str(module.name).lower().replace("pretalx ", ""),
        ),
    )


def plugin_group_key(plugin):
    return getattr(plugin, "category", "OTHER")


def plugin_sort_key(plugin):
    return str(plugin.name).lower().replace("pretalx ", "")


def get_all_plugins_grouped(event=None, filter_visible=True):
    """Return a dict of all plugins found in the installed Django apps,
    grouped by category. If an event is provided, only plugins active for
    that event are returned.
    The key is a tuple of the category name and the human-readable label."""
    plugins = get_all_plugins(event)
    if filter_visible:
        plugins = [
            plugin
            for plugin in plugins
            if not plugin.name.startswith(".") and getattr(plugin, "visible", True)
        ]
    plugins_grouped = groupby(sorted(plugins, key=plugin_group_key), plugin_group_key)
    # Only keep categories with at least one plugin and sort the plugins by name.
    plugins_grouped = {
        category: sorted(plugins, key=plugin_sort_key)
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
