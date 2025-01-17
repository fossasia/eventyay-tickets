import logging
import os
from enum import Enum
from importlib.metadata import version
from typing import List, Protocol, TypeVar, Type

import packaging
from django.apps import AppConfig, apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import packaging.requirements


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


class _PluginMeta(Protocol):
    compatibility: str


T = TypeVar('T', bound=_PluginMeta)


def get_all_plugins(event=None) -> List[Type[T]]:
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
            raise ImproperlyConfigured('A pretix plugin config should have a PretixPluginMeta inner class.')

        meta = self.PretixPluginMeta
        if compat_spec := getattr(meta, 'compatibility', None):
            if not isinstance(compat_spec, str):
                raise ImproperlyConfigured("The 'compatibility' attribute of a plugin must be a string.")
            if os.getenv('PRETIX_IGNORE_CONFLICTS') != 'True':
                check_compatibility(compat_spec)


def check_compatibility(compat_spec: str):
    """
    Checks for compatibility of the plugin based on specified version requirements.

    This method verifies if the currently installed versions of required packages match
    the versions specified in the plugin's compatibility requirements. If a version
    mismatch is found or a required package is not installed, it prints an error message
    and exits the program.

    Raises:
        ImproperlyConfigured: If a version conflict or missing package is detected.
    """
    if not compat_spec:
        return
    req = packaging.requirements.Requirement(compat_spec)
    installed = version(req.name)
    if installed not in req.specifier:
        logger.error(
            'Incompatible plugins found! Plugin %s requires you to have %s, but you installed %s',
            req.name,
            req.specifier,
            installed,
        )
        raise ImproperlyConfigured(f'{req.name} requires {req.specifier}, but you installed {installed}')
