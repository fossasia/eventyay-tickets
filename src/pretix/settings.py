import configparser
import logging
import os
import sys
from urllib.parse import urlparse

import django.conf.locale
import importlib_metadata
from django.contrib.messages import constants as messages  # NOQA
from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _  # NOQA
from kombu import Queue
from pycountry import currencies

from . import __version__
from .helpers.config import EnvOrParserConfig
from .settings_helpers import build_db_tls_config, build_redis_tls_config

_config = configparser.RawConfigParser()
if 'PRETIX_CONFIG_FILE' in os.environ:
    _config.read_file(open(os.environ.get('PRETIX_CONFIG_FILE'), encoding='utf-8'))
else:
    _config.read(
        ['/etc/pretix/pretix.cfg', os.path.expanduser('~/.pretix.cfg'), 'pretix.cfg'],
        encoding='utf-8',
    )
config = EnvOrParserConfig(_config)

CONFIG_FILE = config
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = config.get('pretix', 'datadir', fallback=os.environ.get('DATA_DIR', 'data'))
LOG_DIR = os.path.join(DATA_DIR, 'logs')
MEDIA_ROOT = os.path.join(DATA_DIR, 'media')
PROFILE_DIR = os.path.join(DATA_DIR, 'profiles')

if not os.path.exists(DATA_DIR):
    os.mkdir(DATA_DIR)
if not os.path.exists(LOG_DIR):
    os.mkdir(LOG_DIR)
if not os.path.exists(MEDIA_ROOT):
    os.mkdir(MEDIA_ROOT)

if config.has_option('django', 'secret'):
    SECRET_KEY = config.get('django', 'secret')
else:
    SECRET_FILE = os.path.join(DATA_DIR, '.secret')
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, 'r') as f:
            SECRET_KEY = f.read().strip()
    else:
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
        SECRET_KEY = get_random_string(50, chars)
        with open(SECRET_FILE, 'w') as f:
            os.chmod(SECRET_FILE, 0o600)
            try:
                os.chown(SECRET_FILE, os.getuid(), os.getgid())
            except AttributeError:
                pass  # os.chown is not available on Windows
            f.write(SECRET_KEY)

# Adjustable settings

debug_fallback = 'runserver' in sys.argv
DEBUG = config.getboolean('django', 'debug', fallback=debug_fallback)
LOG_CSP = config.getboolean('pretix', 'csp_log', fallback=True)
CSP_ADDITIONAL_HEADER = config.get('pretix', 'csp_additional_header', fallback='')

PDFTK = config.get('tools', 'pdftk', fallback=None)

PRETIX_AUTH_BACKENDS = config.get('pretix', 'auth_backends', fallback='pretix.base.auth.NativeAuthBackend').split(',')

db_backend = config.get('database', 'backend', fallback='sqlite3')
if db_backend == 'postgresql_psycopg2':
    db_backend = 'postgresql'
if db_backend == 'mysql':
    raise ImproperlyConfigured('MySQL/MariaDB is not supported')

JSON_FIELD_AVAILABLE = db_backend == 'postgresql'
db_options = {}

db_tls_config = build_db_tls_config(config, db_backend)
if db_tls_config is not None:
    db_options.update(db_tls_config)


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.' + db_backend,
        'NAME': config.get('database', 'name', fallback=os.path.join(DATA_DIR, 'db.sqlite3')),
        'USER': config.get('database', 'user', fallback=''),
        'PASSWORD': config.get('database', 'password', fallback=''),
        'HOST': config.get('database', 'host', fallback=''),
        'PORT': config.get('database', 'port', fallback=''),
        'CONN_MAX_AGE': 0 if db_backend == 'sqlite3' else 120,
        'OPTIONS': db_options,
        'TEST': {},
    }
}
DATABASE_REPLICA = 'default'
if config.has_section('replica'):
    DATABASE_REPLICA = 'replica'
    DATABASES['replica'] = {
        'ENGINE': 'django.db.backends.' + db_backend,
        'NAME': config.get('replica', 'name', fallback=DATABASES['default']['NAME']),
        'USER': config.get('replica', 'user', fallback=DATABASES['default']['USER']),
        'PASSWORD': config.get('replica', 'password', fallback=DATABASES['default']['PASSWORD']),
        'HOST': config.get('replica', 'host', fallback=DATABASES['default']['HOST']),
        'PORT': config.get('replica', 'port', fallback=DATABASES['default']['PORT']),
        'CONN_MAX_AGE': 0 if db_backend == 'sqlite3' else 120,
        'OPTIONS': db_options,
        'TEST': {},
    }
    DATABASE_ROUTERS = ['pretix.helpers.database.ReplicaRouter']

BASE_PATH = config.get('pretix', 'base_path', fallback='/tickets')

FORCE_SCRIPT_NAME = BASE_PATH

STATIC_URL = config.get('urls', 'static', fallback=BASE_PATH + '/static/')

MEDIA_URL = config.get('urls', 'media', fallback=BASE_PATH + '/media/')

INSTANCE_NAME = config.get('pretix', 'instance_name', fallback='eventyay')
INSTANCE_NAME_COMMON = config.get('pretix', 'instance_name_common', fallback='eventyay-common')
PRETIX_REGISTRATION = config.getboolean('pretix', 'registration', fallback=True)
PRETIX_PASSWORD_RESET = config.getboolean('pretix', 'password_reset', fallback=True)
PRETIX_LONG_SESSIONS = config.getboolean('pretix', 'long_sessions', fallback=True)
PRETIX_ADMIN_AUDIT_COMMENTS = config.getboolean('pretix', 'audit_comments', fallback=False)
PRETIX_OBLIGATORY_2FA = config.getboolean('pretix', 'obligatory_2fa', fallback=False)
PRETIX_SESSION_TIMEOUT_RELATIVE = 3600 * 3
PRETIX_SESSION_TIMEOUT_ABSOLUTE = 3600 * 12
PRETIX_PRIMARY_COLOR = '#2185d0'
TALK_HOSTNAME = config.get('pretix', 'talk_hostname', fallback='https://wikimania-dev.eventyay.com/')
VIDEO_SERVER_HOSTNAME = config.get('pretix', 'video_server_hostname', fallback='https://app.eventyay.com/video')

SITE_URL = config.get('pretix', 'url', fallback='http://localhost')
if SITE_URL.endswith('/'):
    SITE_URL = SITE_URL[:-1]

CSRF_TRUSTED_ORIGINS = [urlparse(SITE_URL).scheme + '://' + urlparse(SITE_URL).hostname]

TRUST_X_FORWARDED_FOR = config.get('pretix', 'trust_x_forwarded_for', fallback=False)

if config.get('pretix', 'trust_x_forwarded_proto', fallback=False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

PRETIX_PLUGINS_DEFAULT = config.get(
    'pretix',
    'plugins_default',
    fallback='pretix.plugins.sendmail,pretix.plugins.statistics,pretix.plugins.checkinlists,pretix.plugins.autocheckin',
)
PRETIX_PLUGINS_EXCLUDE = config.get('pretix', 'plugins_exclude', fallback='').split(',')

FETCH_ECB_RATES = config.getboolean('pretix', 'ecb_rates', fallback=True)

DEFAULT_CURRENCY = config.get('pretix', 'currency', fallback='EUR')
CURRENCIES = list(currencies)
CURRENCY_PLACES = {
    # default is 2
    'BIF': 0,
    'CLP': 0,
    'DJF': 0,
    'GNF': 0,
    'JPY': 0,
    'KMF': 0,
    'KRW': 0,
    'MGA': 0,
    'PYG': 0,
    'RWF': 0,
    'VND': 0,
    'VUV': 0,
    'XAF': 0,
    'XOF': 0,
    'XPF': 0,
}

ALLOWED_HOSTS = ['*']

LANGUAGE_CODE = config.get('locale', 'default', fallback='en')
TIME_ZONE = config.get('locale', 'timezone', fallback='UTC')

MAIL_FROM = SERVER_EMAIL = DEFAULT_FROM_EMAIL = config.get('mail', 'from', fallback='pretix@localhost')
EMAIL_HOST = config.get('mail', 'host', fallback='localhost')
EMAIL_PORT = config.getint('mail', 'port', fallback=25)
EMAIL_HOST_USER = config.get('mail', 'user', fallback='')
EMAIL_HOST_PASSWORD = config.get('mail', 'password', fallback='')
EMAIL_USE_TLS = config.getboolean('mail', 'tls', fallback=False)
EMAIL_USE_SSL = config.getboolean('mail', 'ssl', fallback=False)
EMAIL_SUBJECT_PREFIX = '[pretix] '

ADMINS = [('Admin', n) for n in config.get('mail', 'admins', fallback='').split(',') if n]

METRICS_ENABLED = config.getboolean('metrics', 'enabled', fallback=False)
METRICS_USER = config.get('metrics', 'user', fallback='metrics')
METRICS_PASSPHRASE = config.get('metrics', 'passphrase', fallback='')

CACHES = {
    'default': {
        'BACKEND': 'pretix.helpers.cache.CustomDummyCache',
    }
}
REAL_CACHE_USED = False
SESSION_ENGINE = None

HAS_MEMCACHED = config.has_option('memcached', 'location')
if HAS_MEMCACHED:
    REAL_CACHE_USED = True
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': config.get('memcached', 'location'),
    }

HAS_REDIS = config.has_option('redis', 'location')
if HAS_REDIS:
    redis_options = {
        'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        'REDIS_CLIENT_KWARGS': {'health_check_interval': 30},
    }
    redis_tls_config = build_redis_tls_config(config)
    if redis_tls_config is not None:
        redis_options['CONNECTION_POOL_KWARGS'] = redis_tls_config
        redis_options['REDIS_CLIENT_KWARGS'].update(redis_tls_config)

    if config.has_option('redis', 'password'):
        redis_options['PASSWORD'] = config.get('redis', 'password')

    CACHES['redis'] = {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config.get('redis', 'location'),
        'OPTIONS': redis_options,
    }
    CACHES['redis_sessions'] = {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config.get('redis', 'location'),
        'TIMEOUT': 3600 * 24 * 30,
        'OPTIONS': redis_options,
    }
    if not HAS_MEMCACHED:
        CACHES['default'] = CACHES['redis']
        REAL_CACHE_USED = True
    if config.getboolean('redis', 'sessions', fallback=False):
        SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
        SESSION_CACHE_ALIAS = 'redis_sessions'

if not SESSION_ENGINE:
    if REAL_CACHE_USED:
        SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
    else:
        SESSION_ENGINE = 'django.contrib.sessions.backends.db'

HAS_CELERY = config.has_option('celery', 'broker')
if HAS_CELERY:
    CELERY_BROKER_URL = config.get('celery', 'broker')
    CELERY_RESULT_BACKEND = config.get('celery', 'backend')
else:
    CELERY_TASK_ALWAYS_EAGER = True

SESSION_COOKIE_DOMAIN = config.get('pretix', 'cookie_domain', fallback=None)

CACHE_TICKETS_HOURS = config.getint('cache', 'tickets', fallback=24 * 3)

ENTROPY = {
    'order_code': config.getint('entropy', 'order_code', fallback=5),
    'ticket_secret': config.getint('entropy', 'ticket_secret', fallback=32),
    'voucher_code': config.getint('entropy', 'voucher_code', fallback=16),
    'giftcard_secret': config.getint('entropy', 'giftcard_secret', fallback=12),
}

# Internal settings
PRETIX_EMAIL_NONE_VALUE = 'info@eventyay.com'

STATIC_ROOT = os.path.join(os.path.dirname(__file__), 'static.dist')

SESSION_COOKIE_NAME = 'pretix_session'
LANGUAGE_COOKIE_NAME = 'pretix_language'
CSRF_COOKIE_NAME = 'pretix_csrftoken'
SESSION_COOKIE_HTTPONLY = True

INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'pretix.base',
    'pretix.control',
    'pretix.presale',
    'pretix.multidomain',
    'pretix.api',
    'pretix.helpers',
    'rest_framework',
    'django_filters',
    'compressor',
    'bootstrap3',
    'djangoformsetjs',
    'pretix.plugins.socialauth',
    'pretix.plugins.banktransfer',
    'pretix.plugins.ticketoutputpdf',
    'pretix.plugins.sendmail',
    'pretix.plugins.statistics',
    'pretix.plugins.reports',
    'pretix.plugins.checkinlists',
    'pretix.plugins.pretixdroid',
    'pretix.plugins.badges',
    'pretix.plugins.manualpayment',
    'pretix.plugins.returnurl',
    'pretix.plugins.webcheckin',
    'pretix.plugins.scheduledtasks',
    'django_markup',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'statici18n',
    'django_countries',
    'hijack',
    'oauth2_provider',
    'phonenumber_field',
    'pretix.eventyay_common',
    'django_celery_beat',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    'allauth.socialaccount.providers.mediawiki',
]

if db_backend == 'postgresql':
    # ALlow plugins to use django.contrib.postgres
    INSTALLED_APPS.insert(0, 'django.contrib.postgres')

try:
    import django_extensions  # noqa

    INSTALLED_APPS.append('django_extensions')
except ImportError:
    pass

PLUGINS = []
entry_points = importlib_metadata.entry_points()

for entry_point in entry_points.select(group='pretix.plugin'):
    if entry_point.module not in PRETIX_PLUGINS_EXCLUDE:
        PLUGINS.append(entry_point.module)
        INSTALLED_APPS.append(entry_point.module)

HIJACK_PERMISSION_CHECK = 'hijack.permissions.superusers_and_staff'
HIJACK_INSERT_BEFORE = None


REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'pretix.api.auth.permission.EventPermission',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'PAGE_SIZE': 50,
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'pretix.api.auth.token.TeamTokenAuthentication',
        'pretix.api.auth.device.DeviceTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
    ),
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'TEST_REQUEST_RENDERER_CLASSES': [
        'rest_framework.renderers.MultiPartRenderer',
        'rest_framework.renderers.JSONRenderer',
        'pretix.testutils.api.UploadRenderer',
    ],
    'EXCEPTION_HANDLER': 'pretix.api.exception.custom_exception_handler',
    'UNICODE_JSON': False,
}


CORE_MODULES = {
    'pretix.base',
    'pretix.presale',
    'pretix.control',
    'pretix.plugins.checkinlists',
    'pretix.plugins.reports',
}

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'pretix.api.middleware.IdempotencyMiddleware',
    'pretix.multidomain.middlewares.MultiDomainMiddleware',
    'pretix.base.middleware.CustomCommonMiddleware',
    'pretix.multidomain.middlewares.SessionMiddleware',
    'pretix.multidomain.middlewares.CsrfViewMiddleware',
    'oauth2_provider.middleware.OAuth2TokenMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'pretix.control.middleware.PermissionMiddleware',
    'pretix.control.middleware.AuditLogMiddleware',
    'pretix.base.middleware.LocaleMiddleware',
    'pretix.base.middleware.SecurityMiddleware',
    'pretix.presale.middleware.EventMiddleware',
    'pretix.api.middleware.ApiScopeMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# Configure CORS for testing

# Configure the authentication backends
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'oauth2_provider.backends.OAuth2Backend',  # Required for OAuth2 authentication
    'allauth.account.auth_backends.AuthenticationBackend',
)


try:
    import debug_toolbar.settings  # noqa

    if DEBUG:
        INSTALLED_APPS.append('debug_toolbar.apps.DebugToolbarConfig')
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        DEBUG_TOOLBAR_PATCH_SETTINGS = False
        DEBUG_TOOLBAR_CONFIG = {
            'JQUERY_URL': '',
            'DISABLE_PANELS': debug_toolbar.settings.PANELS_DEFAULTS,
        }
    pass
except ImportError:
    pass


if METRICS_ENABLED:
    MIDDLEWARE.insert(
        MIDDLEWARE.index('pretix.base.middleware.CustomCommonMiddleware') + 1,
        'pretix.helpers.metrics.middleware.MetricsMiddleware',
    )


PROFILING_RATE = config.getfloat('django', 'profile', fallback=0)  # Percentage of requests to profile
if PROFILING_RATE > 0:
    if not os.path.exists(PROFILE_DIR):
        os.mkdir(PROFILE_DIR)
    MIDDLEWARE.insert(0, 'pretix.helpers.profile.middleware.CProfileMiddleware')


# Security settings
X_FRAME_OPTIONS = 'DENY'

# URL settings
ROOT_URLCONF = 'pretix.multidomain.maindomain_urlconf'

WSGI_APPLICATION = 'pretix.wsgi.application'

USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = [
    os.path.join(os.path.dirname(__file__), 'locale'),
]
if config.has_option('languages', 'path'):
    LOCALE_PATHS.insert(0, config.get('languages', 'path'))

FORMAT_MODULE_PATH = [
    'pretix.helpers.formats',
]

ALL_LANGUAGES = [
    ('en', _('English')),
    ('de', _('German')),
    ('de-formal', _('German (informal)')),
    ('ar', _('Arabic')),
    ('zh-hans', _('Chinese (simplified)')),
    ('da', _('Danish')),
    ('nl', _('Dutch')),
    ('nl-informal', _('Dutch (informal)')),
    ('fr', _('French')),
    ('fi', _('Finnish')),
    ('el', _('Greek')),
    ('it', _('Italian')),
    ('lv', _('Latvian')),
    ('pl', _('Polish')),
    ('pt-pt', _('Portuguese (Portugal)')),
    ('pt-br', _('Portuguese (Brazil)')),
    ('ru', _('Russian')),
    ('es', _('Spanish')),
    ('sw', _('Swahili')),
    ('tr', _('Turkish')),
    ('uk', _('Ukrainian')),
]
LANGUAGES_OFFICIAL = {'en', 'de', 'de-formal'}
LANGUAGES_INCUBATING = {'pl', 'fi', 'pt-br'} - set(config.get('languages', 'allow_incubating', fallback='').split(','))
LANGUAGES_RTL = {'ar', 'hw'}

if DEBUG:
    LANGUAGES = ALL_LANGUAGES
else:
    LANGUAGES = [(k, v) for k, v in ALL_LANGUAGES if k not in LANGUAGES_INCUBATING]


EXTRA_LANG_INFO = {
    'de-formal': {
        'bidi': False,
        'code': 'de-formal',
        'name': 'German (informal)',
        'name_local': 'Deutsch',
        'public_code': 'de',
    },
    'nl-informal': {
        'bidi': False,
        'code': 'nl-informal',
        'name': 'Dutch (informal)',
        'name_local': 'Nederlands',
        'public_code': 'nl',
    },
    'fr': {'bidi': False, 'code': 'fr', 'name': 'French', 'name_local': 'Français'},
    'lv': {'bidi': False, 'code': 'lv', 'name': 'Latvian', 'name_local': 'Latviešu'},
    'pt-pt': {
        'bidi': False,
        'code': 'pt-pt',
        'name': 'Portuguese',
        'name_local': 'Português',
    },
    'sw': {
        'bid': False,
        'code': 'sw',
        'name': _('Swahili'),
        'name_local': 'Kiswahili',
    },
}

django.conf.locale.LANG_INFO.update(EXTRA_LANG_INFO)


AUTH_USER_MODEL = 'pretixbase.User'
LOGIN_URL = 'control:auth.login'
LOGIN_URL_CONTROL = 'control:auth.login'
CSRF_FAILURE_VIEW = 'pretix.base.views.errors.csrf_failure'

template_loaders = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)
if not DEBUG:
    template_loaders = (('django.template.loaders.cached.Loader', template_loaders),)

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
                'django.template.context_processors.request',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
                'pretix.base.context.contextprocessor',
                'pretix.control.context.contextprocessor',
                'pretix.presale.context.contextprocessor',
                'pretix.eventyay_common.context.contextprocessor',
                'django.template.context_processors.request',
            ],
            'loaders': template_loaders,
        },
    },
]

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

STATICFILES_DIRS = (
    [os.path.join(BASE_DIR, 'pretix/static')] if os.path.exists(os.path.join(BASE_DIR, 'pretix/static')) else []
)

STATICI18N_ROOT = os.path.join(BASE_DIR, 'pretix/static')

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# if os.path.exists(os.path.join(DATA_DIR, 'static')):
#     STATICFILES_DIRS.insert(0, os.path.join(DATA_DIR, 'static'))

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
    ('text/vue', 'pretix.helpers.compressor.VueCompiler'),
)

COMPRESS_ENABLED = COMPRESS_OFFLINE = not debug_fallback

COMPRESS_CSS_FILTERS = (
    # CssAbsoluteFilter is incredibly slow, especially when dealing with our _flags.scss
    # However, we don't need it if we consequently use the static() function in Sass
    # 'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSCompressorFilter',
)

INTERNAL_IPS = ('127.0.0.1', '::1')

MESSAGE_TAGS = {
    messages.INFO: 'alert-info',
    messages.ERROR: 'alert-danger',
    messages.WARNING: 'alert-warning',
    messages.SUCCESS: 'alert-success',
}
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

loglevel = 'DEBUG' if DEBUG else config.get('pretix', 'loglevel', fallback='INFO')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {'format': '%(levelname)s %(asctime)s %(name)s %(module)s %(message)s'},
    },
    'filters': {
        'require_admin_enabled': {
            '()': 'pretix.helpers.logs.AdminExistsFilter',
        }
    },
    'handlers': {
        'console': {
            'level': loglevel,
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
        'csp_file': {
            'level': loglevel,
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'csp.log'),
            'formatter': 'default',
        },
        'file': {
            'level': loglevel,
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'pretix.log'),
            'formatter': 'default',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_admin_enabled'],
        },
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['file', 'console'],
            'level': loglevel,
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file', 'console', 'mail_admins'],
            'level': loglevel,
            'propagate': True,
        },
        'pretix.security.csp': {
            'handlers': ['csp_file'],
            'level': loglevel,
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file', 'console', 'mail_admins'],
            'level': loglevel,
            'propagate': True,
        },
        'django.security.DisallowedHost': {
            'handlers': ['null'],
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['file', 'console'],
            'level': 'INFO',  # Do not output all the queries
            'propagate': False,
        },
        'asyncio': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
        },
    },
}

SENTRY_ENABLED = False
if config.has_option('sentry', 'dsn') and not any(c in sys.argv for c in ('shell', 'shell_scoped', 'shell_plus')):
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.logging import (
        LoggingIntegration,
        ignore_logger,
    )
    from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

    from .sentry import PretixSentryIntegration, setup_custom_filters

    SENTRY_TOKEN = config.get('sentry', 'traces_sample_token', fallback='')
    denylist = DEFAULT_DENYLIST + ['access_token', 'sentry_dsn']

    def traces_sampler(context):
        qs = context.get('wsgi_environ', {}).get('QUERY_STRING', '')
        if SENTRY_TOKEN and SENTRY_TOKEN in qs:
            return 1.0
        return config.getfloat('sentry', 'traces_sample_rate', fallback=0.0)

    SENTRY_ENABLED = True
    sentry_sdk.init(
        dsn=config.get('sentry', 'dsn'),
        integrations=[
            PretixSentryIntegration(),
            CeleryIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.CRITICAL),
        ],
        environment=SITE_URL,
        release=__version__,
        send_default_pii=False,
        traces_sampler=traces_sampler,
        event_scrubber=EventScrubber(denylist=denylist, recursive=True),
        propagate_traces=False,
    )
    ignore_logger('pretix.base.tasks')
    ignore_logger('django.security.DisallowedHost')
    setup_custom_filters()

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_QUEUES = (
    Queue('default', routing_key='default.#'),
    Queue('checkout', routing_key='checkout.#'),
    Queue('mail', routing_key='mail.#'),
    Queue('background', routing_key='background.#'),
    Queue('notifications', routing_key='notifications.#'),
)
CELERY_TASK_ROUTES = (
    [
        ('pretix.base.services.cart.*', {'queue': 'checkout'}),
        ('pretix.base.services.orders.*', {'queue': 'checkout'}),
        ('pretix.base.services.mail.*', {'queue': 'mail'}),
        ('pretix.base.services.update_check.*', {'queue': 'background'}),
        ('pretix.base.services.quotas.*', {'queue': 'background'}),
        ('pretix.base.services.waitinglist.*', {'queue': 'background'}),
        ('pretix.base.services.notifications.*', {'queue': 'notifications'}),
        ('pretix.api.webhooks.*', {'queue': 'notifications'}),
        ('pretix.presale.style.*', {'queue': 'background'}),
        ('pretix.plugins.banktransfer.*', {'queue': 'background'}),
    ],
)

BILLING_REMINDER_SCHEDULE = [15, 29]  # Remind on the 15th and 28th day of the month

BOOTSTRAP3 = {
    'success_css_class': '',
    'field_renderers': {
        'default': 'bootstrap3.renderers.FieldRenderer',
        'inline': 'bootstrap3.renderers.InlineFieldRenderer',
        'control': 'pretix.control.forms.renderers.ControlFieldRenderer',
        'bulkedit': 'pretix.control.forms.renderers.BulkEditFieldRenderer',
        'bulkedit_inline': 'pretix.control.forms.renderers.InlineBulkEditFieldRenderer',
        'checkout': 'pretix.presale.forms.renderers.CheckoutFieldRenderer',
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
OAUTH2_PROVIDER_APPLICATION_MODEL = 'pretixapi.OAuthApplication'
OAUTH2_PROVIDER_GRANT_MODEL = 'pretixapi.OAuthGrant'
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = 'pretixapi.OAuthAccessToken'
OAUTH2_PROVIDER_ID_TOKEN_MODEL = 'pretixapi.OAuthIDToken'
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = 'pretixapi.OAuthRefreshToken'
OAUTH2_PROVIDER = {
    'SCOPES': {
        'profile': _('User profile only'),
        'read': _('Read access'),
        'write': _('Write access'),
    },
    'OAUTH2_VALIDATOR_CLASS': 'pretix.api.oauth.Validator',
    'ALLOWED_REDIRECT_URI_SCHEMES': ['https'] if not DEBUG else ['http', 'https'],
    'ACCESS_TOKEN_EXPIRE_SECONDS': 3600 * 24,
    'ROTATE_REFRESH_TOKEN': False,
    'PKCE_REQUIRED': False,
    'OIDC_RESPONSE_TYPES_SUPPORTED': ['code'],  # We don't support proper OIDC for now
}

COUNTRIES_OVERRIDE = {
    'XK': _('Kosovo'),
}

DATA_UPLOAD_MAX_NUMBER_FIELDS = 25000
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

HAS_GEOIP = False
if config.has_option('geoip', 'path'):
    HAS_GEOIP = True
    GEOIP_PATH = config.get('geoip', 'path')
    GEOIP_COUNTRY = config.get('geoip', 'filename_country', fallback='GeoLite2-Country.mmdb')

# Django allauth settings for social login
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'

SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_ADAPTER = 'pretix.plugins.socialauth.adapter.CustomSocialAccountAdapter'
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True
