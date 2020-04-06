import configparser
import os
import sys
from urllib.parse import urlparse

from django.contrib import messages
from django.utils.crypto import get_random_string

# AUTH_USER_MODEL = "core.User"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("STAYSEATED_DATA_DIR", os.path.join(BASE_DIR, "data"))
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
if "STAYSEATED_CONFIG_FILE" in os.environ:
    config.read_file(open(os.environ.get("STAYSEATED_CONFIG_FILE"), encoding="utf-8"))
else:
    config.read(
        [
            "/etc/stayseated/stayseated.cfg",
            os.path.expanduser("~/.stayseated.cfg"),
            "stayseated.cfg",
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
DEBUG = os.environ.get("STAYSEATED_DEBUG", str(debug_default)) == "True"

MAIL_FROM = SERVER_EMAIL = DEFAULT_FROM_EMAIL = os.environ.get(
    "STAYSEATED_MAIL_FROM", config.get("mail", "from", fallback="admin@localhost")
)
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_HOST = os.environ.get(
        "STAYSEATED_MAIL_HOST", config.get("mail", "host", fallback="localhost")
    )
    EMAIL_PORT = int(
        os.environ.get("STAYSEATED_MAIL_PORT", config.get("mail", "port", fallback="25"))
    )
    EMAIL_HOST_USER = os.environ.get(
        "STAYSEATED_MAIL_USER", config.get("mail", "user", fallback="")
    )
    EMAIL_HOST_PASSWORD = os.environ.get(
        "STAYSEATED_MAIL_PASSWORD", config.get("mail", "password", fallback="")
    )
    EMAIL_USE_TLS = os.environ.get("STAYSEATED_MAIL_TLS", "False") == "True"
    EMAIL_USE_SSL = os.environ.get("STAYSEATED_MAIL_SSL", "False") == "True"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends."
                  + os.getenv(
            "STAYSEATED_DB_TYPE", config.get("database", "backend", fallback="sqlite3")
        ),
        "NAME": os.getenv(
            "STAYSEATED_DB_NAME", config.get("database", "name", fallback="db.sqlite3")
        ),
        "USER": os.getenv(
            "STAYSEATED_DB_USER", config.get("database", "user", fallback="")
        ),
        "PASSWORD": os.getenv(
            "STAYSEATED_DB_PASS", config.get("database", "password", fallback="")
        ),
        "HOST": os.getenv(
            "STAYSEATED_DB_HOST", config.get("database", "host", fallback="")
        ),
        "PORT": os.getenv(
            "STAYSEATED_DB_PORT", config.get("database", "port", fallback="")
        ),
        "CONN_MAX_AGE": 0,
    }
}

SITE_URL = os.getenv(
    "STAYSEATED_SITE_URL", config.get("stayseated", "url", fallback="http://localhost")
)
if SITE_URL == "http://localhost" or DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [urlparse(SITE_URL).netloc]

if os.getenv("STAYSEATED_COOKIE_DOMAIN", ""):
    SESSION_COOKIE_DOMAIN = os.getenv("STAYSEATED_COOKIE_DOMAIN", "")
    CSRF_COOKIE_DOMAIN = os.getenv("STAYSEATED_COOKIE_DOMAIN", "")

SESSION_COOKIE_SECURE = (
        os.getenv("STAYSEATED_HTTPS", "True" if SITE_URL.startswith("https:") else "False")
        == "True"
)

CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
SESSION_ENGINE = "django.contrib.sessions.backends.db"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "channels",
    "stayseated.core.CoreConfig",
]

try:
    import django_extensions  # noqa

    INSTALLED_APPS.append("django_extensions")
except ImportError:
    pass

MIDDLEWARE = [
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "stayseated.urls"

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
            os.path.join(BASE_DIR, "stayseated/web/templates"),
        ],
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
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

WSGI_APPLICATION = "stayseated.wsgi.application"
ASGI_APPLICATION = "stayseated.routing.application"

if not DEBUG:
    AUTH_PASSWORD_VALIDATORS = [
        {
            "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        },
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ]

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

SESSION_COOKIE_NAME = "stayseated_session"
CSRF_COOKIE_NAME = "stayseated_csrftoken"
SESSION_COOKIE_HTTPONLY = True

DEBUG_TOOLBAR_PATCH_SETTINGS = False

DEBUG_TOOLBAR_CONFIG = {
    "JQUERY_URL": "",
}

INTERNAL_IPS = ("127.0.0.1", "::1")

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

MESSAGE_TAGS = {
    messages.INFO: "alert-info",
    messages.ERROR: "alert-danger",
    messages.WARNING: "alert-warning",
    messages.SUCCESS: "alert-success",
}

loglevel = "DEBUG" if DEBUG else "INFO"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(levelname)s %(asctime)s %(name)s %(module)s %(message)s"
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
            "filename": os.path.join(LOG_DIR, "stayseated.log"),
            "formatter": "default",
        },
    },
    "loggers": {
        "": {"handlers": ["file", "console"], "level": loglevel, "propagate": True},
        "django.request": {
            "handlers": ["file", "console"],
            "level": loglevel,
            "propagate": True,
        },
        "django.security": {
            "handlers": ["file", "console"],
            "level": loglevel,
            "propagate": True,
        },
        "django.db.backends": {
            "handlers": ["file", "console"],
            "level": "INFO",  # Do not output all the queries
            "propagate": True,
        },
    },
}

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        # TODO
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "PAGE_SIZE": 50,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "UNICODE_JSON": False,
}

STATIC_URL = "/static/"
MEDIA_URL = "/media/"

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

STATICFILES_DIRS = (
    [os.path.join(BASE_DIR, "stayseated/static")]
    if os.path.exists(os.path.join(BASE_DIR, "stayseated/static"))
    else []
)

STATICI18N_ROOT = os.path.join(BASE_DIR, "stayseated/static")

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login"
LOGOUT_REDIRECT_URL = "/accounts/login"
