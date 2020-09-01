import configparser
import os
import sys
from urllib.parse import urlparse

from django.utils.crypto import get_random_string
from kombu import Queue

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("VENUELESS_DATA_DIR", os.path.join(BASE_DIR, "data"))
LOG_DIR = os.path.join(DATA_DIR, "logs")
MEDIA_ROOT = os.path.join(DATA_DIR, "media")
STATIC_ROOT = os.path.join(os.path.dirname(__file__), "static.dist")
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o775
FILE_UPLOAD_PERMISSIONS = 0o644

if not os.path.exists(DATA_DIR):
    os.mkdir(DATA_DIR)
if not os.path.exists(LOG_DIR):
    os.mkdir(LOG_DIR)
if not os.path.exists(MEDIA_ROOT):
    os.mkdir(MEDIA_ROOT)

config = configparser.RawConfigParser()
if "VENUELESS_CONFIG_FILE" in os.environ:
    config.read_file(open(os.environ.get("VENUELESS_CONFIG_FILE"), encoding="utf-8"))
else:
    config.read(
        [
            "/etc/venueless/venueless.cfg",
            os.path.expanduser("~/.venueless.cfg"),
            "venueless.cfg",
        ],
        encoding="utf-8",
    )

SECRET_FILE = os.path.join(DATA_DIR, ".secret")
if os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, "r") as f:
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

debug_default = "runserver" in sys.argv
DEBUG = os.environ.get("VENUELESS_DEBUG", str(debug_default)) == "True"

MAIL_FROM = SERVER_EMAIL = DEFAULT_FROM_EMAIL = os.environ.get(
    "VENUELESS_MAIL_FROM", config.get("mail", "from", fallback="admin@localhost")
)
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_HOST = os.environ.get(
        "VENUELESS_MAIL_HOST", config.get("mail", "host", fallback="localhost")
    )
    EMAIL_PORT = int(
        os.environ.get("VENUELESS_MAIL_PORT", config.get("mail", "port", fallback="25"))
    )
    EMAIL_HOST_USER = os.environ.get(
        "VENUELESS_MAIL_USER", config.get("mail", "user", fallback="")
    )
    EMAIL_HOST_PASSWORD = os.environ.get(
        "VENUELESS_MAIL_PASSWORD", config.get("mail", "password", fallback="")
    )
    EMAIL_USE_TLS = os.environ.get("VENUELESS_MAIL_TLS", "False") == "True"
    EMAIL_USE_SSL = os.environ.get("VENUELESS_MAIL_SSL", "False") == "True"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends."
        + os.getenv(
            "VENUELESS_DB_TYPE",
            config.get("database", "backend", fallback="postgresql"),
        ),
        "NAME": os.getenv(
            "VENUELESS_DB_NAME", config.get("database", "name", fallback="venueless")
        ),
        "USER": os.getenv(
            "VENUELESS_DB_USER", config.get("database", "user", fallback="venueless")
        ),
        "PASSWORD": os.getenv(
            "VENUELESS_DB_PASS", config.get("database", "password", fallback="")
        ),
        "HOST": os.getenv(
            "VENUELESS_DB_HOST", config.get("database", "host", fallback="")
        ),
        "PORT": os.getenv(
            "VENUELESS_DB_PORT", config.get("database", "port", fallback="")
        ),
        "CONN_MAX_AGE": 60,
    }
}

redis_auth = os.getenv(
    "VENUELESS_REDIS_AUTH",
    config.get("redis", "auth", fallback=""),
)
redis_url = (
    "redis://"
    + ((":" + redis_auth + "@") if redis_auth else "")
    + os.getenv(
        "VENUELESS_REDIS_HOST",
        config.get("redis", "host", fallback="127.0.0.1"),
    )
    + ":"
    + os.getenv(
        "VENUELESS_REDIS_PORT",
        config.get("redis", "port", fallback="6379"),
    )
    + "/"
    + os.getenv(
        "VENUELESS_REDIS_DB",
        config.get("redis", "db", fallback="0"),
    )
)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [{"address": redis_url}],
            "prefix": "venueless:asgi:",
            "capacity": 10000,
        },
    },
}

SITE_URL = os.getenv(
    "VENUELESS_SITE_URL", config.get("venueless", "url", fallback="http://localhost")
)
if SITE_URL == "http://localhost" or DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [urlparse(SITE_URL).netloc]

if os.getenv("VENUELESS_COOKIE_DOMAIN", ""):
    CSRF_COOKIE_DOMAIN = os.getenv("VENUELESS_COOKIE_DOMAIN", "")

STATIC_URL = os.getenv(
    "VENUELESS_STATIC_URL", config.get("urls", "static", fallback="/static/")
)
MEDIA_URL = os.getenv(
    "VENUELESS_MEDIA_URL", config.get("urls", "media", fallback="/media/")
)

nanocdn = os.getenv("VENUELESS_NANOCDN", config.get("urls", "nanocdn", fallback=""))
if nanocdn:
    NANOCDN_URL = nanocdn
    DEFAULT_FILE_STORAGE = "venueless.platforms.storage.nanocdn.NanoCDNStorage"

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    "process": {
        # LocMemCache is async-safe, other cache backends are not, so we shouldn't ever replace this backend here!
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    },
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "channels",
    "corsheaders",
    "rest_framework",
    "venueless.core.CoreConfig",
    "venueless.api.ApiConfig",
    "venueless.live.LiveConfig",
    "venueless.graphs.GraphsConfig",
    "venueless.storage.StorageConfig",
]

try:
    import django_extensions  # noqa

    INSTALLED_APPS.append("django_extensions")
except ImportError:
    pass

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "venueless.urls"

if DEBUG:
    CORS_ORIGIN_REGEX_WHITELIST = [
        r"^http://localhost$",
        r"^http://localhost:\d+$",
    ]

X_FRAME_OPTIONS = "DENY"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
CSP_DEFAULT_SRC = ("'self'", "'unsafe-eval'")

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
            os.path.join(BASE_DIR, "venueless/web/templates"),
        ],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
            "loaders": template_loaders,
        },
    },
]

WSGI_APPLICATION = "venueless.wsgi.application"
ASGI_APPLICATION = "venueless.routing.application"

LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ("en", "Englisch"),
    ("de", "Deutsch"),
]

LOCALE_PATHS = (os.path.join(os.path.dirname(__file__), "locale"),)

CSRF_COOKIE_NAME = "venueless_csrftoken"

DEBUG_TOOLBAR_PATCH_SETTINGS = False

DEBUG_TOOLBAR_CONFIG = {
    "JQUERY_URL": "",
}

INTERNAL_IPS = ("127.0.0.1", "::1")

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
            "filename": os.path.join(LOG_DIR, "venueless.log"),
            "formatter": "default",
        },
    },
    "loggers": {
        "": {"handlers": ["file", "console"], "level": loglevel, "propagate": True},
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

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "venueless.api.auth.NoPermission",
    ],
    "UNAUTHENTICATED_USER": "venueless.api.auth.AnonymousUser",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "PAGE_SIZE": 50,
    "DEFAULT_AUTHENTICATION_CLASSES": ("venueless.api.auth.WorldTokenAuthentication",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "UNICODE_JSON": False,
}

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

STATICFILES_DIRS = (
    [os.path.join(BASE_DIR, "venueless/static")]
    if os.path.exists(os.path.join(BASE_DIR, "venueless/static"))
    else []
)

STATICI18N_ROOT = os.path.join(BASE_DIR, "venueless/static")

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login"
LOGOUT_REDIRECT_URL = "/accounts/login"

VENUELESS_COMMIT = os.environ.get("VENUELESS_COMMIT_SHA", "unknown")
VENUELESS_ENVIRONMENT = os.environ.get("VENUELESS_ENVIRONMENT", "unknown")

CELERY_BROKER_URL = redis_url
CELERY_RESULT_BACKEND = redis_url
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES = (Queue("default", routing_key="default.#"),)
CELERY_TASK_ALWAYS_EAGER = os.environ.get("VENUELESS_CELERY_EAGER", "") == "true"

SENTRY_DSN = os.environ.get(
    "VENUELESS_SENTRY_DSN", config.get("sentry", "dsn", fallback="")
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
        release=VENUELESS_COMMIT,
        environment=VENUELESS_ENVIRONMENT,
    )

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES = (
    Queue("default", routing_key="default.#"),
    Queue("longrunning", routing_key="longrunning.#"),
)
