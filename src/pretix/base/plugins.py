import importlib.metadata
import logging
import os
import sys
from enum import Enum
from typing import List

from django.apps import AppConfig, apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

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
    Returns the PretixPluginMeta classes of all plugins found in the installed Django apps.
    """
    plugins = []
    for app in apps.get_app_configs():
        if hasattr(app, 'PretixPluginMeta'):
            meta = app.PretixPluginMeta
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


class PluginConfig(AppConfig):
    IGNORE = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'PretixPluginMeta'):
            raise ImproperlyConfigured(
                'A pretix plugin config should have a PretixPluginMeta inner class.'
            )

        if (
            hasattr(self.PretixPluginMeta, 'compatibility')
            and not os.environ.get('PRETIX_IGNORE_CONFLICTS') == 'True'
        ):
            self.check_compatibility()

    def check_compatibility(self):
        """
        Checks for compatibility of the plugin based on specified version requirements.

        This method verifies if the currently installed versions of required packages match
        the versions specified in the plugin's compatibility requirements. If a version
        mismatch is found or a required package is not installed, it prints an error message
        and exits the program.

        Steps:
        1. Iterates over the compatibility requirements specified in `self.PretixPluginMeta.compatibility`.
        2. For each requirement, it splits the package name and the required version.
        3. Fetches the installed version of the package using `importlib.metadata.version`.
        4. Compares the installed version with the required version.
        5. If a mismatch is found, prints an error message and exits the program.
        6. If a required package is not found, catches the `PackageNotFoundError`, prints an error message,
           and exits the program.

        Raises:
            SystemExit: If a version conflict or missing package is detected, the program exits.
        """
        try:
            for requirement in self.PretixPluginMeta.compatibility:
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
