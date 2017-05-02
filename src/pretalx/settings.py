import os

import sys
from urllib.parse import urlparse

from django.contrib.messages import constants as messages  # NOQA
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _  # NOQA


# File system and directory settings
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.getenv('PRETALX_DATA_DIR', os.path.join(BASE_DIR, 'data'))
LOG_DIR = os.path.join(DATA_DIR, 'logs')
MEDIA_ROOT = os.path.join(DATA_DIR, 'media')
STATIC_ROOT = os.path.join(os.path.dirname(__file__), 'static.dist')

if not os.path.exists(DATA_DIR):
    os.mkdir(DATA_DIR)
if not os.path.exists(LOG_DIR):
    os.mkdir(LOG_DIR)
if not os.path.exists(MEDIA_ROOT):
    os.mkdir(MEDIA_ROOT)

SECRET_FILE = os.path.join(DATA_DIR, '.secret')
if os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, 'r') as f:
        SECRET_KEY = f.read().strip()
else:
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    SECRET_KEY = get_random_string(50, chars)
    with open(SECRET_FILE, 'w') as f:
        os.chmod(SECRET_FILE, 0o600)
        os.chown(SECRET_FILE, os.getuid(), os.getgid())
        f.write(SECRET_KEY)

# General setup settings
debug_default = 'runserver' in sys.argv
DEBUG = os.environ.get('PRETALX_DEBUG', str(debug_default)) == 'True'

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    MAIL_FROM = SERVER_EMAIL = DEFAULT_FROM_EMAIL = os.environ.get('PRETALX_MAIL_FROM', 'admin@localhost')
    EMAIL_HOST = os.environ.get('PRETALX_MAIL_HOST', 'localhost')
    EMAIL_PORT = int(os.environ.get('PRETALX_MAIL_PORT', '25'))
    EMAIL_HOST_USER = os.environ.get('PRETALX_MAIL_USER', '')
    EMAIL_HOST_PASSOWRD = os.environ.get('PRETALX_MAIL_PASSWORD', '')
    EMAIL_USE_TLS = os.environ.get('PRETALX_MAIL_TLS', 'False') == 'True'
    EMAIL_USE_SSL = os.environ.get('PRETALX_MAIL_SSL', 'False') == 'True'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.' + os.getenv('PRETALX_DB_TYPE', 'sqlite3'),
        'NAME': os.getenv('PRETALX_DB_NAME', 'db.sqlite3'),
        'USER': os.getenv('PRETALX_DB_USER', ''),
        'PASSWORD': os.getenv('PRETALX_DB_PASS', ''),
        'HOST': os.getenv('PRETALX_DB_HOST', ''),
        'PORT': os.getenv('PRETALX_DB_PORT', ''),
        'CONN_MAX_AGE': 0,
    }
}

STATIC_URL = '/static/'
MEDIA_URL = '/media/'

SITE_URL = os.getenv('PRETALX_SITE_URL', 'http://localhost')
if SITE_URL == 'http://localhost':
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = [urlparse(SITE_URL).netloc]


if os.getenv('PRETALX_COOKIE_DOMAIN', ''):
    SESSION_COOKIE_DOMAIN = os.getenv('PRETALX_COOKIE_DOMAIN', '')
    CSRF_COOKIE_DOMAIN = os.getenv('PRETALX_COOKIE_DOMAIN', '')

SESSION_COOKIE_SECURE = os.getenv('PRETALX_HTTPS', 'True' if SITE_URL.startswith('https:') else 'False') == 'True'


# Internal settings
LANGUAGES = [
    ('en', _('English')),
    ('de', _('German')),
]
LANGUAGES_NATURAL_NAMES = [
    ('en', 'English'),
    ('de', 'Deutsch'),
]
LANGUAGE_CODE = 'en'

LOCALE_PATHS = (
    os.path.join(os.path.dirname(__file__), 'locale'),
)

SESSION_COOKIE_NAME = 'pretalx_session'
CSRF_COOKIE_NAME = 'pretalx_csrftoken'
SESSION_COOKIE_HTTPONLY = True

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'compressor',
    'bootstrap4',
    'pretalx.common',
    'pretalx.event',
    'pretalx.mail',
    'pretalx.person',
    'pretalx.schedule',
    'pretalx.submission',
    'pretalx.orga',
    'pretalx.cfp',
]

try:
    import django_extensions  # noqa
    INSTALLED_APPS.append('django_extensions')
except ImportError:
    pass

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',
    'pretalx.common.middleware.EventPermissionMiddleware',
]

try:
    import debug_toolbar  # noqa
    if DEBUG:
        INSTALLED_APPS.append('debug_toolbar.apps.DebugToolbarConfig')
        MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')
except ImportError:
    pass


# Security settings
X_FRAME_OPTIONS = 'DENY'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
CSP_DEFAULT_SRC = ("'self'",)

# URL settings
ROOT_URLCONF = 'pretalx.urls'

WSGI_APPLICATION = 'pretalx.wsgi.application'

USE_I18N = True
USE_L10N = True
USE_TZ = True

AUTH_USER_MODEL = 'person.User'
LOGIN_URL = '/login'  # global login does not yet exist

template_loaders = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)
if not DEBUG:
    template_loaders = (
        ('django.template.loaders.cached.Loader', template_loaders),
    )

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(DATA_DIR, 'templates'),
            os.path.join(BASE_DIR, 'templates'),
        ],
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                "django.template.context_processors.request",
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
                'pretalx.orga.context_processors.add_events',
            ],
            'loaders': template_loaders
        },
    },
]

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'pretalx', 'static')
] if os.path.exists(os.path.join(BASE_DIR, 'pretalx', 'static')) else []

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

COMPRESS_ENABLED = COMPRESS_OFFLINE = not DEBUG

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
)

COMPRESS_CSS_FILTERS = (
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSCompressorFilter',
)

DEBUG_TOOLBAR_PATCH_SETTINGS = False


DEBUG_TOOLBAR_CONFIG = {
    'JQUERY_URL': '',
}

INTERNAL_IPS = ('127.0.0.1', '::1')

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

loglevel = 'DEBUG' if DEBUG else 'INFO'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(levelname)s %(asctime)s %(name)s %(module)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': loglevel,
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        },
        'file': {
            'level': loglevel,
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'pretalx.log'),
            'formatter': 'default'
        },
    },
    'loggers': {
        '': {
            'handlers': ['file', 'console'],
            'level': loglevel,
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file', 'console'],
            'level': loglevel,
            'propagate': True,
        },
        'django.security': {
            'handlers': ['file', 'console'],
            'level': loglevel,
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': ['file', 'console'],
            'level': 'INFO',  # Do not output all the queries
            'propagate': True,
        }
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

MESSAGE_TAGS = {
    messages.INFO: 'info',
    messages.ERROR: 'danger',
    messages.WARNING: 'warning',
    messages.SUCCESS: 'success',
}
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# For now, to ease development
CELERY_TASK_ALWAYS_EAGER = True
