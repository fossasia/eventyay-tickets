import os
from contextlib import suppress
from urllib.parse import urlparse

from django.contrib.messages import constants as messages
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from pkg_resources import iter_entry_points

from pretalx.common.settings.config import build_config
from pretalx.common.settings.utils import log_initial


config, config_files = build_config()
CONFIG = config

##
# This settings file is rather lengthy. It follows this structure:
# Directories, Apps, Url, Security, Databases, Logging, Email, Caching (and Sessions)
# I18n, Auth, Middleware, Templates and Staticfiles, External Apps
#
# Search for "## {AREA} SETTINGS" to navigate this file
##

DEBUG = config.getboolean('site', 'debug')


## DIRECTORY SETTINGS
BASE_DIR = config.get('filesystem', 'base')
DATA_DIR = config.get(
    'filesystem',
    'data',
    fallback=os.environ.get('PRETALX_DATA_DIR', os.path.join(BASE_DIR, 'data')),
)
LOG_DIR = config.get('filesystem', 'logs', fallback=os.path.join(DATA_DIR, 'logs'))
MEDIA_ROOT = config.get('filesystem', 'media', fallback=os.path.join(DATA_DIR, 'media'))
STATIC_ROOT = config.get(
    'filesystem', 'static', fallback=os.path.join(BASE_DIR, 'static.dist')
)
HTMLEXPORT_ROOT = config.get(
    'filesystem', 'htmlexport', fallback=os.path.join(DATA_DIR, 'htmlexport')
)

for directory in (BASE_DIR, DATA_DIR, LOG_DIR, MEDIA_ROOT, HTMLEXPORT_ROOT):
    os.makedirs(directory, exist_ok=True)


## APP SETTINGS
DJANGO_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
EXTERNAL_APPS = [
    'bakery',
    'compressor',
    'djangoformsetjs',
    'jquery',
    'rest_framework',
    'rest_framework.authtoken',
    'rules',
]
LOCAL_APPS = [
    'pretalx.api',
    'pretalx.common',
    'pretalx.event',
    'pretalx.mail',
    'pretalx.person',
    'pretalx.schedule',
    'pretalx.submission',
    'pretalx.agenda',
    'pretalx.cfp',
    'pretalx.orga',
]
FALLBACK_APPS = ['bootstrap4', 'django.forms']
INSTALLED_APPS = DJANGO_APPS + EXTERNAL_APPS + LOCAL_APPS + FALLBACK_APPS

PLUGINS = []
for entry_point in iter_entry_points(group='pretalx.plugin', name=None):
    PLUGINS.append(entry_point.module_name)
    INSTALLED_APPS.append(entry_point.module_name)

## URL SETTINGS
SITE_URL = config.get('site', 'url', fallback='http://localhost')
SITE_NETLOC = urlparse(SITE_URL).netloc
INTERNAL_IPS = ('127.0.0.1', '::1')
ALLOWED_HOSTS = [
    '*'
]  # We have our own security middleware to allow for custom event URLs

ROOT_URLCONF = 'pretalx.urls'
STATIC_URL = '/static/'
MEDIA_URL = '/media/'


## SECURITY SETTINGS
X_FRAME_OPTIONS = 'DENY'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

CSP_DEFAULT_SRC = "'self'"
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:")

CSRF_COOKIE_NAME = 'pretalx_csrftoken'
CSRF_TRUSTED_ORIGINS = [urlparse(SITE_URL).hostname]
SESSION_COOKIE_NAME = 'pretalx_session'
SESSION_COOKIE_HTTPONLY = True
if config.get('site', 'cookie_domain'):
    SESSION_COOKIE_DOMAIN = CSRF_COOKIE_DOMAIN = config.get('site', 'cookie_domain')

SESSION_COOKIE_SECURE = config.getboolean(
    'site', 'https', fallback=SITE_URL.startswith('https:')
)

if config.has_option('site', 'secret'):
    SECRET_KEY = config.get('site', 'secret')
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
            os.chown(SECRET_FILE, os.getuid(), os.getgid())
            f.write(SECRET_KEY)


## DATABASE SETTINGS
db_backend = config.get('database', 'backend')
db_name = config.get('database', 'name', fallback=os.path.join(DATA_DIR, 'db.sqlite3'))
if db_backend == 'mysql':
    db_opts = {
        'charset': 'utf8mb4',
        'use_unicode': True,
        'init_command': 'SET character_set_connection=utf8mb4,collation_connection=utf8mb4_unicode_ci;',
    }
else:
    db_opts = {}
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.' + db_backend,
        'NAME': db_name,
        'USER': config.get('database', 'user'),
        'PASSWORD': config.get('database', 'password'),
        'HOST': config.get('database', 'host'),
        'PORT': config.get('database', 'port'),
        'CONN_MAX_AGE': 0 if db_backend == 'sqlite3' else 120,
        'OPTIONS': db_opts,
    }
}


## LOGGING SETTINGS
loglevel = 'DEBUG' if DEBUG else 'INFO'
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(levelname)s %(asctime)s %(name)s %(module)s %(message)s'
        }
    },
    'handlers': {
        'console': {
            'level': loglevel,
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
        'file': {
            'level': loglevel,
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'pretalx.log'),
            'formatter': 'default',
        },
    },
    'loggers': {
        '': {'handlers': ['file', 'console'], 'level': loglevel, 'propagate': True},
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
        },
    },
}

email_level = config.get('logging', 'email_level', fallback='ERROR') or 'ERROR'
emails = config.get('logging', 'email', fallback='').split(',')
MANAGERS = ADMINS = [(email, email) for email in emails if email]
if ADMINS:
    LOGGING['handlers']['mail_admins'] = {
        'level': email_level,
        'class': 'django.utils.log.AdminEmailHandler',
    }


## EMAIL SETTINGS
MAIL_FROM = SERVER_EMAIL = DEFAULT_FROM_EMAIL = config.get('mail', 'from')
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_HOST = config.get('mail', 'host')
    EMAIL_PORT = config.get('mail', 'port')
    EMAIL_HOST_USER = config.get('mail', 'user')
    EMAIL_HOST_PASSWORD = config.get('mail', 'password')
    EMAIL_USE_TLS = config.getboolean('mail', 'tls')
    EMAIL_USE_SSL = config.getboolean('mail', 'ssl')


## CACHE SETTINGS
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}
REAL_CACHE_USED = False
SESSION_ENGINE = None

HAS_MEMCACHED = bool(os.getenv('PRETALX_MEMCACHE', ''))
if HAS_MEMCACHED:
    REAL_CACHE_USED = True
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': os.getenv('PRETALX_MEMCACHE'),
    }

HAS_REDIS = config.get('redis', 'location') != 'False'
if HAS_REDIS:
    CACHES['redis'] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config.get('redis', 'location'),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
    CACHES['redis_sessions'] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config.get('redis', 'location'),
        "TIMEOUT": 3600 * 24 * 30,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
    if not HAS_MEMCACHED:
        CACHES['default'] = CACHES['redis']
        REAL_CACHE_USED = True

    if config.getboolean('redis', 'session'):
        SESSION_ENGINE = "django.contrib.sessions.backends.cache"
        SESSION_CACHE_ALIAS = "redis_sessions"

if not SESSION_ENGINE:
    if REAL_CACHE_USED:
        SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
    else:
        SESSION_ENGINE = "django.contrib.sessions.backends.db"

HAS_CELERY = bool(config.get('celery', 'broker', fallback=None))
if HAS_CELERY:
    CELERY_BROKER_URL = config.get('celery', 'broker')
    CELERY_RESULT_BACKEND = config.get('celery', 'backend')
else:
    CELERY_TASK_ALWAYS_EAGER = True
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
MESSAGE_TAGS = {
    messages.INFO: 'info',
    messages.ERROR: 'danger',
    messages.WARNING: 'warning',
    messages.SUCCESS: 'success',
}


## I18N SETTINGS
USE_I18N = True
USE_L10N = True
USE_TZ = True
LANGUAGES = [('en', _('English')), ('de', _('German')), ('fr', _('French'))]
LANGUAGES_NATURAL_NAMES = [('en', 'English'), ('de', 'Deutsch'), ('fr', 'Français')]
LANGUAGE_CODE = 'en'
LANGUAGES_OFFICIAL = {'en', 'de'}
LOCALE_PATHS = (os.path.join(os.path.dirname(__file__), 'locale'),)
FORMAT_MODULE_PATH = ['pretalx.common.formats']


## AUTHENTICATION SETTINGS
AUTH_USER_MODEL = 'person.User'
LOGIN_URL = '/orga/login'
AUTHENTICATION_BACKENDS = (
    'rules.permissions.ObjectPermissionBackend',
    'django.contrib.auth.backends.ModelBackend',
    'pretalx.common.auth.AuthenticationTokenBackend',
)
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'
    },
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


## MIDDLEWARE SETTINGS
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',  # Security first
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Next up: static files
    'django.middleware.common.CommonMiddleware',  # Set some sensible defaults, now, before responses are modified
    'pretalx.common.middleware.SessionMiddleware',  # Add session handling
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # Uses sessions
    'pretalx.common.auth.AuthenticationTokenMiddleware',  # Make auth tokens work
    'pretalx.common.middleware.MultiDomainMiddleware',  # Check which host is used and if it is valid
    'pretalx.common.middleware.EventPermissionMiddleware',  # Sets locales, request.event, available events, etc.
    'pretalx.common.middleware.CsrfViewMiddleware',  # Protect against CSRF attacks before forms/data are processed
    'django.contrib.messages.middleware.MessageMiddleware',  # Uses sessions
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # Protects against clickjacking
    'csp.middleware.CSPMiddleware',  # Modifies/sets CSP headers
]


## TEMPLATE AND STATICFILES SETTINGS
template_loaders = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)
if not DEBUG:
    template_loaders = (('django.template.loaders.cached.Loader', template_loaders),)

FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'
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
                'pretalx.common.context_processors.add_events',
                'pretalx.common.context_processors.locale_context',
                'pretalx.common.context_processors.messages',
                'pretalx.common.context_processors.system_information',
                'pretalx.orga.context_processors.orga_events',
            ],
            'loaders': template_loaders,
        },
    }
]

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)
STATICFILES_DIRS = (
    [os.path.join(BASE_DIR, 'pretalx', 'static')]
    if os.path.exists(os.path.join(BASE_DIR, 'pretalx', 'static'))
    else []
)

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


## EXTERNAL APP SETTINGS
with suppress(ImportError):
    import django_extensions  # noqa

    INSTALLED_APPS.append('django_extensions')
with suppress(ImportError):
    import debug_toolbar  # noqa

    if DEBUG:
        INSTALLED_APPS.append('debug_toolbar.apps.DebugToolbarConfig')
        MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')
BOOTSTRAP4 = {
    'field_renderers': {
        'default': 'bootstrap4.renderers.FieldRenderer',
        'inline': 'bootstrap4.renderers.InlineFieldRenderer',
        'event': 'pretalx.common.forms.renderers.EventFieldRenderer',
        'event-inline': 'pretalx.common.forms.renderers.EventInlineFieldRenderer',
    }
}
DEBUG_TOOLBAR_PATCH_SETTINGS = False
DEBUG_TOOLBAR_CONFIG = {'JQUERY_URL': ''}
COMPRESS_ENABLED = COMPRESS_OFFLINE = not DEBUG
COMPRESS_PRECOMPILERS = (('text/x-scss', 'django_libsass.SassCompiler'),)
COMPRESS_CSS_FILTERS = (
    # CssAbsoluteFilter is incredibly slow, especially when dealing with our _flags.scss
    # However, we don't need it if we consequently use the static() function in Sass
    # 'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSCompressorFilter',
)

# django-bakery / HTML export
BUILD_DIR = HTMLEXPORT_ROOT
BAKERY_VIEWS = (
    'pretalx.agenda.views.htmlexport.ExportScheduleView',
    'pretalx.agenda.views.htmlexport.ExportFrabXmlView',
    'pretalx.agenda.views.htmlexport.ExportFrabXCalView',
    'pretalx.agenda.views.htmlexport.ExportFrabJsonView',
    'pretalx.agenda.views.htmlexport.ExportICalView',
    'pretalx.agenda.views.htmlexport.ExportScheduleVersionsView',
    'pretalx.agenda.views.htmlexport.ExportTalkView',
    'pretalx.agenda.views.htmlexport.ExportTalkICalView',
    'pretalx.agenda.views.htmlexport.ExportSpeakerView',
)
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ('i18nfield.rest_framework.I18nJSONRenderer',),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    # 'DEFAULT_PERMISSION_CLASSES': ('pretalx.api.permissions.ApiPermission',)
    'DEFAULT_FILTER_BACKENDS': (
        'rest_framework.filters.SearchFilter',
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 25,
    'SEARCH_PARAM': 'q',
    'ORDERING_PARAM': 'o',
    'VERSIONING_PARAM': 'v',
}
if DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] += (
        'rest_framework.renderers.BrowsableAPIRenderer',
    )
    REST_FRAMEWORK['COMPACT_JSON'] = False

WSGI_APPLICATION = 'pretalx.wsgi.application'
log_initial(
    debug=DEBUG,
    config_files=config_files,
    db_name=db_name,
    db_backend=db_backend,
    LOG_DIR=LOG_DIR,
    plugins=PLUGINS,
)
