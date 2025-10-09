import importlib.metadata
import logging
import os
import sys
from enum import Enum
from itertools import groupby
from typing import List

from django.apps import AppConfig, apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

logger = logging.getLogger(__name__)


class PluginType(Enum):
    """
    Plugin type classification. THIS IS DEPRECATED, DO NOT USE ANY MORE.
    This is only not removed yet as external plugins might have references
    to this enum.
    """

    RESTRICTION = 1
    PAYMENT = 2
    ADMINFEATURE = 3
    EXPORT = 4


def get_all_plugins(event=None) -> List[type]:
    """
    Returns the EventyayPluginMeta classes of all plugins found in the installed Django apps.
    If an event is provided, only plugins active for that event are returned.
    """
    plugins = []
    for app in apps.get_app_configs():
        if hasattr(app, 'EventyayPluginMeta'):
            meta = app.EventyayPluginMeta
            meta.module = app.name
            meta.app = app
            if app.name in settings.PRETIX_PLUGINS_EXCLUDE:
                continue

            if hasattr(app, 'is_available') and event:
                if not app.is_available(event):
                    continue

            plugins.append(meta)
    return sorted(
        plugins,
        key=lambda m: (
            0 if m.module.startswith('pretix.') else 1,
            str(m.name).lower().replace('pretix ', ''),
        ),
    )


# from eventyay-talk
CATEGORY_LABELS = {
    'FEATURE': pgettext_lazy('Type of plugin', 'Features'),
    'INTEGRATION': pgettext_lazy('Type of plugin', 'Integrations'),
    'CUSTOMIZATION': pgettext_lazy('Type of plugin', 'Customizations'),
    'EXPORTER': _('Exporters'),
    'RECORDING': _('Recording integrations'),
    'LANGUAGE': _('Languages'),
    'OTHER': pgettext_lazy('category of products', 'Other'),
}


# from eventyay-talk
def plugin_group_key(plugin):
    return getattr(plugin, 'category', 'OTHER')


# from eventyay-talk
def plugin_sort_key(plugin):
    return str(plugin.name).lower().replace('pretalx ', '')


# from eventyay-talk
def get_all_plugins_grouped(event=None, filter_visible=True):
    """
    Return a dict of all plugins found in the installed Django apps, grouped by category.
    If an event is provided, only plugins active for that event are returned.
    The key is a tuple of the category name and the human-readable label.
    """
    plugins = get_all_plugins(event)
    if filter_visible:
        plugins = [plugin for plugin in plugins if not plugin.name.startswith('.') and getattr(plugin, 'visible', True)]
    plugins_grouped = groupby(sorted(plugins, key=plugin_group_key), plugin_group_key)
    # Only keep categories with at least one plugin and sort the plugins by name.
    plugins_grouped = {
        category: sorted(plugins, key=plugin_sort_key) for category, plugins in plugins_grouped if plugins
    }

    # Replace the category keys with the translated labels and sort accordingly.
    return {
        (category, CATEGORY_LABELS[category]): plugins_grouped[category]
        for category in CATEGORY_LABELS
        if category in plugins_grouped
    }


class PluginConfig(AppConfig):
    IGNORE = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'EventyayPluginMeta'):
            raise ImproperlyConfigured('A pretix plugin config should have a EventyayPluginMeta inner class.')

        if hasattr(self.EventyayPluginMeta, 'compatibility') and not os.environ.get('PRETIX_IGNORE_CONFLICTS') == 'True':
            self.check_compatibility()

    def check_compatibility(self):
        """
        Checks for compatibility of the plugin based on specified version requirements.
        Exits the program if incompatibility is detected.
        """
        try:
            for requirement in self.EventyayPluginMeta.compatibility:
                package_name, _, required_version = requirement.partition('==')
                installed_version = importlib.metadata.version(package_name)
                if installed_version != required_version:
                    logger.error('Incompatible plugins found!')
                    logger.error(
                        'Plugin %s requires you to have %s==%s, but you installed %s==%s',
                        self.name,
                        package_name,
                        required_version,
                        package_name,
                        installed_version,
                    )
                    sys.exit(1)
        except importlib.metadata.PackageNotFoundError as e:
            logger.exception(f'Package not found: {e}')
            sys.exit(1)
