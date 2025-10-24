"""
DEPRECATED: This module is deprecated. Use eventyay.config.asgi instead.

This file is kept for backwards compatibility with deployments that reference
eventyay.config.routing:application. New deployments should use:
    daphne eventyay.config.asgi:application

Routing configuration is now properly separated:
- asgi.py: Main ASGI entry point with Django initialization
- features/live/routing.py: WebSocket URL patterns
"""

import warnings

warnings.warn(
    'eventyay.config.routing is deprecated. Use eventyay.config.asgi instead. '
    'Update your Daphne command to: daphne eventyay.config.asgi:application',
    DeprecationWarning,
    stacklevel=2
)

# Import the application from the proper location
from eventyay.config.asgi import application  # noqa: F401

__all__ = ['application']
