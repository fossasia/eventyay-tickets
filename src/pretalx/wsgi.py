"""WSGI config for pretalx.

Use with gunicorn or uwsgi.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pretalx.settings")

from django.core.wsgi import get_wsgi_application  # NOQA

try:
    from dj_static import Cling, MediaCling

    application = Cling(MediaCling(get_wsgi_application()))
except ImportError:
    application = get_wsgi_application()
