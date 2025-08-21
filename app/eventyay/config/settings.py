"""
Django settings for config project.
"""
import configparser
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from django.utils.translation import gettext_lazy as _
from django.utils.crypto import get_random_string
from kombu import Queue
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from eventyay.helpers.config import EnvOrParserConfig
from .settings_helpers import build_db_tls_config, build_redis_tls_config
from pycountry import currencies

# Base directory configurations
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = os.environ.get("EVENTYAY_DATA_DIR", os.path.join(BASE_DIR, "data"))
LOG_DIR = os.path.join(DATA_DIR, "logs")
MEDIA_ROOT = os.path.join(DATA_DIR, "media")
STATIC_ROOT = os.path.join(os.path.dirname(__file__), "static.dist")
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o775
FILE_UPLOAD_PERMISSIONS = 0o644

# Create necessary directories
if not os.path.exists(DATA_DIR):
    os.mkdir(DATA_DIR)
if not os.path.exists(LOG_DIR):
    os.mkdir(LOG_DIR)
if not os.path.exists(MEDIA_ROOT):
    os.mkdir(MEDIA_ROOT)

# Configuration file handling
config = configparser.RawConfigParser()
_config = configparser.RawConfigParser()

if "EVENTYAY_CONFIG_FILE" in os.environ:
    config.read_file(open(os.environ.get("EVENTYAY_CONFIG_FILE"), encoding="utf-8"))
    _config.read_file(open(os.environ.get('EVENTYAY_CONFIG_FILE'), encoding='utf-8'))
else:
    config.read(
        [
            "/etc/eventyay/eventyay.cfg",
            os.path.expanduser("~/.eventyay.cfg"),
            "eventyay.cfg",
        ],
        encoding="utf-8",
    )
    _config.read(
        ['/etc/eventyay/eventyay.cfg', os.path.expanduser('~/.eventyay.cfg'), 'eventyay.cfg'],
        encoding='utf-8',
    )

eventyay_config = EnvOrParserConfig(_config)

def instance_name(request):
    from django.conf import settings
    return {
        'INSTANCE_NAME': getattr(settings, 'INSTANCE_NAME', 'eventyay')
    }
# Secret key configuration (Eventyay style)
SECRET_KEY = os.environ.get(
    "EVENTYAY_DJANGO_SECRET", config.get("django", "secret", fallback="")
)
if not SECRET_KEY:
    # Fallback to Eventyay secret key
    SECRET_KEY = 'django-insecure-_sesosamnd81fm%go!+5inrmln^p1c%b&$abp6j(lw8$xx(ria'
    
    SECRET_FILE = os.path.join(DATA_DIR, ".secret")
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE) as f:
            SECRET_KEY = f.read().strip()
    else:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
        SECRET_KEY = get_random_string(50, chars)
        with open(SECRET_FILE, "w") as f:
            os.chmod(SECRET_FILE, 0o600)
            try:
                os.chown(SECRET_FILE, os.getuid(), os.getgid())
            except AttributeError:
                pass  # os.chown is not available on Windows
            f.write(SECRET_KEY)

# Path configurations
BASE_PATH = config.get("eventyay", "base_path", fallback="")
DOMAIN_PATH = config.get(
    "eventyay", "domain_path", fallback="https://app.eventyay.com"
)

# Site URL configuration
SITE_URL = os.getenv(
    "EVENTYAY_SITE_URL",
    config.get("eventyay", "url", fallback=eventyay_config.get('eventyay', 'url', fallback='http://localhost')),
)

# Debug configuration
debug_default = "runserver" in sys.argv
DEBUG = os.environ.get("EVENTYAY_DEBUG", str(debug_default)) == "True"

# Hosts configuration
ALLOWED_HOSTS = []
X_FRAME_OPTIONS = 'DENY'

# URL settings
# ROOT_URLCONF = 'eventyay.multidomain.maindomain_urlconf'

# Multifactor authentication
EVENTYAY_MULTIFACTOR_REQUIRE = (
    os.environ.get(
        "EVENTYAY_MULTIFACTOR_REQUIRE",
        str(config.getboolean("eventyay", "multifactor_require", fallback=False)),
    )
    == "True"
)

# User model
AUTH_USER_MODEL = 'eventyaybase.User'

# Email configuration
MAIL_FROM = SERVER_EMAIL = DEFAULT_FROM_EMAIL = os.environ.get(
    "EVENTYAY_MAIL_FROM",
    config.get("mail", "from", fallback=eventyay_config.get('mail', 'from', fallback='eventyay@localhost')),
)

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_HOST = os.environ.get(
        "EVENTYAY_MAIL_HOST", config.get("mail", "host", fallback="localhost")
    )
    EMAIL_PORT = int(
        os.environ.get("EVENTYAY_MAIL_PORT", config.get("mail", "port", fallback="25"))
    )
    EMAIL_HOST_USER = os.environ.get(
        "EVENTYAY_MAIL_USER", config.get("mail", "user", fallback="")
    )
    EMAIL_HOST_PASSWORD = os.environ.get(
        "EVENTYAY_MAIL_PASSWORD", config.get("mail", "password", fallback="")
    )
    EMAIL_USE_TLS = os.environ.get("EVENTYAY_MAIL_TLS", "False") == "True"
    EMAIL_USE_SSL = os.environ.get("EVENTYAY_MAIL_SSL", "False") == "True"

# Database configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends."
        + os.getenv(
            "EVENTYAY_DB_TYPE",
            config.get("database", "backend", fallback="postgresql"),
        ),
        "NAME": os.getenv(
            "EVENTYAY_DB_NAME",
            config.get("database", "name", fallback="eventyay"),
        ),
        "USER": os.getenv(
            "EVENTYAY_DB_USER", config.get("database", "user", fallback="")
        ),
        "PASSWORD": os.getenv(
            "EVENTYAY_DB_PASS",
            config.get("database", "password", fallback=""),
        ),
        "HOST": os.getenv(
            "EVENTYAY_DB_HOST", config.get("database", "host", fallback="")
        ),
        "PORT": os.getenv(
            "EVENTYAY_DB_PORT", config.get("database", "port", fallback="")
        ),
        "CONN_MAX_AGE": 0,
    }
}

# Fallback to SQLite if no database configured
if not DATABASES["default"]["NAME"] or DATABASES["default"]["NAME"] == "eventyay":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'HOST': config.get('database', 'host', fallback=''),
        }
    }

# Redis configuration
redis_connection_kwargs = {
    "retry": Retry(ExponentialBackoff(), 3),
    "health_check_interval": 120,
}

if os.getenv("EVENTYAY_REDIS_URLS", config.get("redis", "urls", fallback="")):
    REDIS_HOSTS = [
        {"address": u, **redis_connection_kwargs}
        for u in os.getenv(
            "EVENTYAY_REDIS_URLS", config.get("redis", "urls", fallback="")
        ).split(",")
    ]
else:
    redis_auth = os.getenv(
        "EVENTYAY_REDIS_AUTH",
        config.get("redis", "auth", fallback=""),
    )
    redis_url = (
        "redis://"
        + ((":" + redis_auth + "@") if redis_auth else "")
        + os.getenv(
            "EVENTYAY_REDIS_HOST",
            config.get("redis", "host", fallback="127.0.0.1"),
        )
        + ":"
        + os.getenv(
            "EVENTYAY_REDIS_PORT",
            config.get("redis", "port", fallback="6379"),
        )
        + "/"
        + os.getenv(
            "EVENTYAY_REDIS_DB",
            config.get("redis", "db", fallback="0"),
        )
    )
    REDIS_HOSTS = [{"address": redis_url, **redis_connection_kwargs}]

REDIS_USE_PUBSUB = os.getenv(
    "EVENTYAY_REDIS_USE_PUBSUB",
    config.get("redis", "use_pubsub", fallback="false"),
) in (True, "yes", "on", "true", "True", "1")

# Channel layers configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": (
            "channels_redis.pubsub.RedisPubSubChannelLayer"
            if REDIS_USE_PUBSUB
            else "channels_redis.core.RedisChannelLayer"
        ),
        "CONFIG": {
            "hosts": REDIS_HOSTS,
            "prefix": "eventyay:{}:asgi:".format(
                config.get("redis", "db", fallback="0")
            ),
            "capacity": 10000,
        },
    },
}

# URL configurations
SHORT_URL = os.getenv(
    "EVENTYAY_SHORT_URL",
    config.get("eventyay", "short_url", fallback=SITE_URL),
)

if os.getenv("EVENTYAY_COOKIE_DOMAIN", ""):
    CSRF_COOKIE_DOMAIN = os.getenv("EVENTYAY_COOKIE_DOMAIN", "")

STATIC_URL = os.getenv(
    "EVENTYAY_STATIC_URL", config.get("urls", "static", fallback="/static/")
)
MEDIA_URL = os.getenv(
    "EVENTYAY_MEDIA_URL", config.get("urls", "media", fallback="/media/")
)
TALK_BASE_PATH = config.get(
    "urls", "eventyay-talk", fallback="https://app-test.eventyay.com/talk"
)

WEBSOCKET_PROTOCOL = os.getenv(
    "EVENTYAY_WEBSOCKET_PROTOCOL",
    config.get("websocket", "protocol", fallback="wss"),
)

# Storage configuration
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

nanocdn = os.getenv("EVENTYAY_NANOCDN", config.get("urls", "nanocdn", fallback=""))
if nanocdn:
    NANOCDN_URL = nanocdn
    STORAGES["default"][
        "BACKEND"
    ] = "eventyay.base.integrations.platforms.storage.nanocdn.NanoCDNStorage"

# Third-party service configurations
ZOOM_KEY = os.getenv("EVENTYAY_ZOOM_KEY", config.get("zoom", "key", fallback=""))
ZOOM_SECRET = os.getenv(
    "EVENTYAY_ZOOM_SECRET", config.get("zoom", "secret", fallback="")
)

CONTROL_SECRET = os.getenv(
    "EVENTYAY_CONTROL_SECRET", config.get("control", "secret", fallback="")
)

STATSD_HOST = os.getenv(
    "EVENTYAY_STATSD_HOST", config.get("statsd", "host", fallback="")
)
STATSD_PORT = os.getenv(
    "EVENTYAY_STATSD_PORT", config.get("statsd", "port", fallback="9125")
)
STATSD_PREFIX = "eventyay"

TWITTER_CLIENT_ID = os.getenv(
    "EVENTYAY_TWITTER_CLIENT_ID",
    config.get("twitter", "client_id", fallback=""),
)
TWITTER_CLIENT_SECRET = os.getenv(
    "EVENTYAY_TWITTER_CLIENT_SECRET",
    config.get("twitter", "client_secret", fallback=""),
)
LINKEDIN_CLIENT_ID = os.getenv(
    "EVENTYAY_LINKEDIN_CLIENT_ID",
    config.get("linkedin", "client_id", fallback=""),
)
LINKEDIN_CLIENT_SECRET = os.getenv(
    "EVENTYAY_LINKEDIN_CLIENT_SECRET",
    config.get("linkedin", "client_secret", fallback=""),
)

# Cache configuration (merged from both projects)
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    "process": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    },
}

# Eventyay cache configurations
REAL_CACHE_USED = False
SESSION_ENGINE = None

HAS_MEMCACHED = eventyay_config.has_option('memcached', 'location')
if HAS_MEMCACHED:
    REAL_CACHE_USED = True
    CACHES['memcached'] = {
        'BACKEND': 'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': eventyay_config.get('memcached', 'location'),
    }

HAS_REDIS = eventyay_config.has_option('redis', 'location')
if HAS_REDIS:
    redis_options = {
        'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        'REDIS_CLIENT_KWARGS': {'health_check_interval': 30},
    }
    redis_tls_config = build_redis_tls_config(eventyay_config)
    if redis_tls_config is not None:
        redis_options['CONNECTION_POOL_KWARGS'] = redis_tls_config
        redis_options['REDIS_CLIENT_KWARGS'].update(redis_tls_config)

    if eventyay_config.has_option('redis', 'password'):
        redis_options['PASSWORD'] = eventyay_config.get('redis', 'password')

    CACHES['redis'] = {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': eventyay_config.get('redis', 'location'),
        'OPTIONS': redis_options,
    }
    CACHES['redis_sessions'] = {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': eventyay_config.get('redis', 'location'),
        'TIMEOUT': 3600 * 24 * 30,
        'OPTIONS': redis_options,
    }
    if not HAS_MEMCACHED:
        CACHES['default'] = CACHES['redis']
        REAL_CACHE_USED = True
    if eventyay_config.getboolean('redis', 'sessions', fallback=False):
        SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
        SESSION_CACHE_ALIAS = 'redis_sessions'

if not SESSION_ENGINE:
    if REAL_CACHE_USED:
        SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
    else:
        SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Installed apps (merged from both projects)
INSTALLED_APPS = [
    "daphne",
    "bootstrap3",
    "compressor",
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "channels",
    "corsheaders",
    "rest_framework",
    "djangoformsetjs",
    "oauth2_provider",
    "eventyay.core.CoreConfig",
    "eventyay.api",
    "eventyay.features.live.LiveConfig",
    "eventyay.features.analytics.graphs.GraphsConfig",
    "eventyay.features.importers.ImportersConfig",
    "eventyay.storage.StorageConfig",
    "eventyay.features.social.SocialConfig",
    "eventyay.features.integrations.zoom.ZoomConfig",
    "eventyay.control.ControlConfig",
    "eventyay.base",
    "eventyay.common",
    "eventyay.eventyay_common",
    "eventyay.helpers",
    "eventyay.multidomain",
    "eventyay.presale",
    "multifactor",
    "statici18n",
]

try:
    import django_extensions  # noqa
    INSTALLED_APPS.append("django_extensions")
except ImportError:
    pass

# Middleware (merged from both projects)
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'eventyay.base.middleware.CustomCommonMiddleware',
    'eventyay.base.middleware.LocaleMiddleware',
    'eventyay.base.middleware.SecurityMiddleware',
    'eventyay.multidomain.middlewares.MultiDomainMiddleware',
    'eventyay.multidomain.middlewares.SessionMiddleware',
    'eventyay.multidomain.middlewares.CsrfViewMiddleware',
    'eventyay.control.middleware.PermissionMiddleware',
    'eventyay.control.middleware.AuditLogMiddleware',
    "eventyay.control.video.middleware.SessionMiddleware",
    "eventyay.control.video.middleware.AuthenticationMiddleware",
    "eventyay.control.video.middleware.MessageMiddleware",
]

ROOT_URLCONF = "eventyay.config.urls"
# ROOT_URLCONF = 'eventyay.multidomain.maindomain_urlconf'

# CORS configuration
CORS_ORIGIN_REGEX_WHITELIST = [
    r"^https?://([\w\-]+\.)?eventyay\.com$",
    r"^https?://app-test\.eventyay\.com(:\d+)?$",
    r"^https?://app\.eventyay\.com(:\d+)?$",
]
if DEBUG:
    CORS_ORIGIN_REGEX_WHITELIST = [
        r"^http://localhost$",
        r"^http://localhost:\d+$",
    ]

# Security settings
X_FRAME_OPTIONS = "DENY"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
CSP_DEFAULT_SRC = ("'self'", "'unsafe-eval'")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# Template configuration
template_loaders = (
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
)
if not DEBUG:
    template_loaders = (("django.template.loaders.cached.Loader", template_loaders),)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(DATA_DIR, "templates"),
            os.path.join(BASE_DIR, "templates"),
            os.path.join(BASE_DIR, "eventyay/web/templates"),
        ],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                'config.settings.instance_name',
            ],
            "loaders": template_loaders,
        },
    },
]

# WSGI/ASGI applications
WSGI_APPLICATION = "eventyay.config.wsgi.application"
ASGI_APPLICATION = "eventyay.config.routing.application"

# Internationalization
LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("de", "Deutsch"),
]

LOCALE_PATHS = (os.path.join(os.path.dirname(__file__), "locale"),)


# Internal settings
SESSION_COOKIE_NAME = 'eventyay_session'
LANGUAGE_COOKIE_NAME = 'eventyay_language'
CSRF_COOKIE_NAME = 'eventyay_csrftoken'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_DOMAIN = config.get('eventyay', 'cookie_domain', fallback=None)


# Debug toolbar configuration
DEBUG_TOOLBAR_PATCH_SETTINGS = False
DEBUG_TOOLBAR_CONFIG = {
    "JQUERY_URL": "",
}
INTERNAL_IPS = ("127.0.0.1", "::1")

# Logging configuration
loglevel = "DEBUG" if DEBUG else "INFO"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(thread)d %(name)s %(module)s %(message)s"
        },
    },
    "handlers": {
        "console": {
            "level": loglevel,
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "file": {
            "level": loglevel,
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "eventyay.log"),
            "formatter": "default",
        },
    },
    "loggers": {
        "": {
            "handlers": ["file", "console"],
            "level": loglevel,
            "propagate": True,
        },
        "django.request": {
            "handlers": ["file", "console"],
            "level": loglevel,
            "propagate": False,
        },
        "django.security": {
            "handlers": ["file", "console"],
            "level": loglevel,
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["file", "console"],
            "level": loglevel,
            "propagate": False,
        },
    },
}

if DEBUG:
    import logging
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

# REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "eventyay.base.api.auth.NoPermission",
    ],
    "UNAUTHENTICATED_USER": "eventyay.base.api.auth.AnonymousUser",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "PAGE_SIZE": 50,
    "DEFAULT_AUTHENTICATION_CLASSES": ("eventyay.api.auth.api_auth.EventTokenAuthentication",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "UNICODE_JSON": False,
}

# Static files configuration
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    'compressor.finders.CompressorFinder',
)

STATICFILES_DIRS = (
    [os.path.join(BASE_DIR, "eventyay/static")]
    if os.path.exists(os.path.join(BASE_DIR, "eventyay/static"))
    else []
)

STATICI18N_ROOT = os.path.join(BASE_DIR, "eventyay/static")

# Login/Logout URLs

LOGIN_REDIRECT_URL = "/control/"

# Version and environment
EVENTYAY_COMMIT = os.environ.get("EVENTYAY_COMMIT_SHA", "unknown")
EVENTYAY_ENVIRONMENT = os.environ.get("EVENTYAY_ENVIRONMENT", "unknown")

# Celery configuration
CELERY_BROKER_URL = REDIS_HOSTS[0]["address"]
CELERY_RESULT_BACKEND = REDIS_HOSTS[0]["address"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES = (
    Queue("default", routing_key="default.#"),
    Queue("longrunning", routing_key="longrunning.#"),
    Queue('background', routing_key='background.#'),
    Queue('notifications', routing_key='notifications.#'),
)
CELERY_TASK_ALWAYS_EAGER = os.environ.get("EVENTYAY_CELERY_EAGER", "") == "true"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ROUTES = (
    [
        ('eventyay.base.services.notifications.*', {'queue': 'notifications'}),
        ('eventyay.api.webhooks.*', {'queue': 'notifications'}),
    ],
)

# Sentry configuration
SENTRY_DSN = os.environ.get(
    "EVENTYAY_SENTRY_DSN", config.get("sentry", "dsn", fallback="")
)
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[CeleryIntegration(), DjangoIntegration()],
        send_default_pii=False,
        debug=DEBUG,
        release=EVENTYAY_COMMIT,
        environment=EVENTYAY_ENVIRONMENT,
    )

# Default auto field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Eventyay specific configurations
ENTROPY = {
    'order_code': eventyay_config.getint('entropy', 'order_code', fallback=5),
    'ticket_secret': eventyay_config.getint('entropy', 'ticket_secret', fallback=32),
    'voucher_code': eventyay_config.getint('entropy', 'voucher_code', fallback=16),
    'giftcard_secret': eventyay_config.getint('entropy', 'giftcard_secret', fallback=12),
}

EVENTYAY_PRIMARY_COLOR = '#2185d0'

DEFAULT_CURRENCY = eventyay_config.get('eventyay', 'currency', fallback='EUR')
CURRENCY_PLACES = {
    'BIF': 0, 'CLP': 0, 'DJF': 0, 'GNF': 0, 'JPY': 0, 'KMF': 0, 'KRW': 0,
    'MGA': 0, 'PYG': 0, 'RWF': 0, 'VND': 0, 'VUV': 0, 'XAF': 0, 'XOF': 0, 'XPF': 0,
}

CURRENCIES = list(currencies)
EVENTYAY_EMAIL_NONE_VALUE = 'info@eventyay.com'
TALK_HOSTNAME = eventyay_config.get('eventyay', 'talk_hostname', fallback='https://wikimania-dev.eventyay.com/')

# Metrics configuration
METRICS_ENABLED = eventyay_config.getboolean('metrics', 'enabled', fallback=False)
METRICS_USER = eventyay_config.get('metrics', 'user', fallback='metrics')
METRICS_PASSPHRASE = eventyay_config.get('metrics', 'passphrase', fallback='')

# Password validation
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

# Multifactor authentication configuration
MULTIFACTOR = {
    "LOGIN_CALLBACK": False,
    "RECHECK": True,
    "RECHECK_MIN": 3600 * 24,
    "RECHECK_MAX": 3600 * 24 * 7,
    "FIDO_SERVER_ID": urlparse(SITE_URL).hostname,
    "FIDO_SERVER_NAME": "Eventyay",
    "TOKEN_ISSUER_NAME": "Eventyay",
    "U2F_APPID": SITE_URL,
    "FACTORS": ["FIDO2"],
    "FALLBACKS": {},
}

# Adjustable settings
INSTANCE_NAME = config.get('eventyay', 'instance_name', fallback='eventyay')
EVENTYAY_REGISTRATION = config.getboolean('eventyay', 'registration', fallback=True)
EVENTYAY_PASSWORD_RESET = config.getboolean('eventyay', 'password_reset', fallback=True)
EVENTYAY_LONG_SESSIONS = config.getboolean('eventyay', 'long_sessions', fallback=True)
EVENTYAY_AUTH_BACKENDS = config.get('eventyay', 'auth_backends', fallback='eventyay.base.auth.NativeAuthBackend').split(',')
EVENTYAY_ADMIN_AUDIT_COMMENTS = config.getboolean('eventyay', 'audit_comments', fallback=False)
EVENTYAY_OBLIGATORY_2FA = config.getboolean('eventyay', 'obligatory_2fa', fallback=False)
EVENTYAY_SESSION_TIMEOUT_RELATIVE = 3600 * 3
EVENTYAY_SESSION_TIMEOUT_ABSOLUTE = 3600 * 12

LOG_CSP = config.getboolean('eventyay', 'csp_log', fallback=True)
CSP_ADDITIONAL_HEADER = config.get('eventyay', 'csp_additional_header', fallback='')

# Django allauth settings for social login
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'

SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True

SOCIALACCOUNT_ADAPTER = 'eventyay.plugins.socialauth.adapter.CustomSocialAccountAdapter'
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True

OAUTH2_PROVIDER_APPLICATION_MODEL = 'eventyayapi.OAuthApplication'
OAUTH2_PROVIDER_GRANT_MODEL = 'eventyayapi.OAuthGrant'
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = 'eventyayapi.OAuthAccessToken'
OAUTH2_PROVIDER_ID_TOKEN_MODEL = 'eventyayapi.OAuthIDToken'
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = 'eventyayapi.OAuthRefreshToken'
OAUTH2_PROVIDER = {
    'SCOPES': {
        'profile': _('User profile only'),
        'read': _('Read access'),
        'write': _('Write access'),
    },
    'OAUTH2_VALIDATOR_CLASS': 'eventyay.api.oauth.Validator',
    'ALLOWED_REDIRECT_URI_SCHEMES': ['https'] if not DEBUG else ['http', 'https'],
    'ACCESS_TOKEN_EXPIRE_SECONDS': 3600 * 24,
    'ROTATE_REFRESH_TOKEN': False,
    'PKCE_REQUIRED': False,
    'OIDC_RESPONSE_TYPES_SUPPORTED': ['code'],  # We don't support proper OIDC for now
}


LOGIN_URL = 'eventyay_common:auth.login'
LOGIN_URL_CONTROL = 'eventyay_common:auth.login'
# CSRF_FAILURE_VIEW = 'eventyay.base.views.errors.csrf_failure'


STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# django-compressor SCSS support
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = not DEBUG
COMPRESS_ROOT = os.path.join(BASE_DIR, 'static/')
COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
)

COMPRESS_CSS_FILTERS = (
    'compressor.filters.cssmin.CSSCompressorFilter',
)