import atexit
import os
import tempfile
from contextlib import suppress

tmpdir = tempfile.TemporaryDirectory()
os.environ.setdefault('DATA_DIR', tmpdir.name)
if os.path.exists('test/sqlite.cfg'):
    os.environ.setdefault('PRETALX_CONFIG_FILE', 'test/sqlite.cfg')

from pretalx.settings import *  # NOQA

BASE_DIR = tmpdir.name
DATA_DIR = tmpdir.name
LOG_DIR = os.path.join(DATA_DIR, 'logs')
MEDIA_ROOT = os.path.join(DATA_DIR, 'media')
STATIC_ROOT = os.path.join(DATA_DIR, 'static')
HTMLEXPORT_ROOT = os.path.join(DATA_DIR, 'htmlexport')

for directory in (BASE_DIR, DATA_DIR, LOG_DIR, MEDIA_ROOT, HTMLEXPORT_ROOT):
    os.makedirs(directory, exist_ok=True)

INSTALLED_APPS.append('tests.dummy_app.PluginApp')  # noqa

atexit.register(tmpdir.cleanup)

EMAIL_BACKEND = 'django.core.mail.outbox'
MAIL_FROM = 'orga@orga.org'

COMPRESS_ENABLED = COMPRESS_OFFLINE = False
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

COMPRESS_PRECOMPILERS_ORIGINAL = COMPRESS_PRECOMPILERS  # NOQA
COMPRESS_PRECOMPILERS = ()  # NOQA
TEMPLATES[0]['OPTIONS']['loaders'] = (  # NOQA
    ('django.template.loaders.cached.Loader', template_loaders),  # NOQA
)

DEBUG = True
DEBUG_PROPAGATE_EXCEPTIONS = True

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Disable celery
CELERY_ALWAYS_EAGER = True
HAS_CELERY = False

# Don't use redis
SESSION_ENGINE = "django.contrib.sessions.backends.db"
HAS_REDIS = False
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

with suppress(ValueError):
    INSTALLED_APPS.remove('debug_toolbar.apps.DebugToolbarConfig')  # noqa
    MIDDLEWARE.remove('debug_toolbar.middleware.DebugToolbarMiddleware')  # noqa


# Don't run migrations
class DisableMigrations(object):

    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


if not os.environ.get("TRAVIS", ""):
    MIGRATION_MODULES = DisableMigrations()
