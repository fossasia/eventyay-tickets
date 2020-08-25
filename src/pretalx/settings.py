import os
from contextlib import suppress
from urllib.parse import urlparse
from pathlib import Path

from django.contrib.messages import constants as messages
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from pkg_resources import iter_entry_points

from pretalx import __version__
from pretalx.common.settings.config import build_config
from pretalx.common.settings.utils import log_initial


config, CONFIG_FILES = build_config()
CONFIG = config

##
# This settings file is rather lengthy. It follows this structure:
# Directories, Apps, Url, Security, Databases, Logging, Email, Caching (and Sessions)
# I18n, Auth, Middleware, Templates and Staticfiles, External Apps
#
# Search for "## {AREA} SETTINGS" to navigate this file
##

DEBUG = config.getboolean("site", "debug")


## DIRECTORY SETTINGS
BASE_DIR = Path(config.get("filesystem", "base"))
DATA_DIR = Path(
    config.get(
        "filesystem",
        "data",
        fallback=os.environ.get("PRETALX_DATA_DIR", BASE_DIR / "data"),
    )
)
LOG_DIR = Path(config.get("filesystem", "logs", fallback=DATA_DIR / "logs"))
MEDIA_ROOT = Path(config.get("filesystem", "media", fallback=DATA_DIR / "media"))
STATIC_ROOT = Path(
    config.get("filesystem", "static", fallback=BASE_DIR / "static.dist",)
)
HTMLEXPORT_ROOT = Path(
    config.get("filesystem", "htmlexport", fallback=DATA_DIR / "htmlexport",)
)

for directory in (BASE_DIR, DATA_DIR, LOG_DIR, MEDIA_ROOT, HTMLEXPORT_ROOT):
    directory.mkdir(parents=True, exist_ok=True)


## APP SETTINGS
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
EXTERNAL_APPS = [
    "compressor",
    "djangoformsetjs",
    "django_filters",
    "jquery",
    "rest_framework.authtoken",
    "rules",
]
LOCAL_APPS = [
    "pretalx.api",
    "pretalx.common",
    "pretalx.event",
    "pretalx.mail",
    "pretalx.person",
    "pretalx.schedule",
    "pretalx.submission",
    "pretalx.agenda",
    "pretalx.cfp",
    "pretalx.orga",
]
FALLBACK_APPS = [
    "bootstrap4",
    "django.forms",
    "rest_framework",
]
INSTALLED_APPS = DJANGO_APPS + EXTERNAL_APPS + LOCAL_APPS + FALLBACK_APPS

PLUGINS = []
for entry_point in iter_entry_points(group="pretalx.plugin", name=None):
    PLUGINS.append(entry_point.module_name)
    INSTALLED_APPS.append(entry_point.module_name)

CORE_MODULES = LOCAL_APPS + [
    module for module in config.get("site", "core_modules").split(",") if module
]


## PLUGIN SETTINGS
PLUGIN_SETTINGS = {}
for section in config.sections():
    if section.startswith("plugin:"):
        PLUGIN_SETTINGS[section[len("plugin:") :]] = dict(config.items(section))


## URL SETTINGS
SITE_URL = config.get("site", "url", fallback="http://localhost")
SITE_NETLOC = urlparse(SITE_URL).netloc
ALLOWED_HOSTS = [
    "*"
]  # We have our own security middleware to allow for custom event URLs

ROOT_URLCONF = "pretalx.urls"
STATIC_URL = config.get("site", "static")
MEDIA_URL = config.get("site", "media")
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
FILE_UPLOAD_DEFAULT_LIMIT = 10 * 1024 * 1024


## SECURITY SETTINGS
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

CSP_DEFAULT_SRC = "'self'"
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:")
CSP_BASE_URI = "'none'"
CSP_FORM_ACTION = "'self'"

CSRF_COOKIE_NAME = "pretalx_csrftoken"
CSRF_TRUSTED_ORIGINS = [urlparse(SITE_URL).hostname]
SESSION_COOKIE_NAME = "pretalx_session"
SESSION_COOKIE_HTTPONLY = True
if config.get("site", "cookie_domain"):
    SESSION_COOKIE_DOMAIN = CSRF_COOKIE_DOMAIN = config.get("site", "cookie_domain")

SESSION_COOKIE_SECURE = config.getboolean(
    "site", "https", fallback=SITE_URL.startswith("https:")
)

if config.has_option("site", "secret"):
    SECRET_KEY = config.get("site", "secret")
else:
    SECRET_FILE = DATA_DIR / ".secret"
    if SECRET_FILE.exists():
        with SECRET_FILE.open() as f:
            SECRET_KEY = f.read().strip()
    else:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
        SECRET_KEY = get_random_string(50, chars)
        with SECRET_FILE.open(mode="w") as f:
            SECRET_FILE.chmod(0o600)
            with suppress(Exception):  # chown is not available on all platforms
                os.chown(SECRET_FILE, os.getuid(), os.getgid())
            f.write(SECRET_KEY)

## TASK RUNNER SETTINGS
HAS_CELERY = bool(config.get("celery", "broker", fallback=None))
if HAS_CELERY:
    CELERY_BROKER_URL = config.get("celery", "broker")
    CELERY_RESULT_BACKEND = config.get("celery", "backend")
else:
    CELERY_TASK_ALWAYS_EAGER = True

## DATABASE SETTINGS
db_backend = config.get("database", "backend")
db_name = config.get("database", "name", fallback=str(DATA_DIR / "db.sqlite3"))
if db_backend == "mysql":
    db_opts = {
        "charset": "utf8mb4",
        "use_unicode": True,
        "init_command": "SET character_set_connection=utf8mb4,collation_connection=utf8mb4_unicode_ci;",
    }
else:
    db_opts = {}
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends." + db_backend,
        "NAME": db_name,
        "USER": config.get("database", "user"),
        "PASSWORD": config.get("database", "password"),
        "HOST": config.get("database", "host"),
        "PORT": config.get("database", "port"),
        "CONN_MAX_AGE": 0 if db_backend == "sqlite3" or HAS_CELERY else 120,
        "OPTIONS": db_opts,
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci",}
        if "mysql" in db_backend
        else {},
    }
}


## LOGGING SETTINGS
loglevel = "DEBUG" if DEBUG else "INFO"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(levelname)s %(asctime)s %(name)s %(module)s %(message)s"
        }
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
            "filename": LOG_DIR / "pretalx.log",
            "formatter": "default",
        },
        "null": {"class": "logging.NullHandler",},
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
            "propagate": True,
        },
        "django.security.DisallowedHost": {"handlers": ["null"], "propagate": False,},
        "django.db.backends": {
            "handlers": ["file", "console"],
            "level": "INFO",  # Do not output all the queries
            "propagate": True,
        },
    },
}

email_level = config.get("logging", "email_level", fallback="ERROR") or "ERROR"
emails = config.get("logging", "email", fallback="").split(",")
DEFAULT_EXCEPTION_REPORTER = "pretalx.common.exceptions.PretalxExceptionReporter"
MANAGERS = ADMINS = [(email, email) for email in emails if email]
MANAGERS = ADMINS = [("rixx@localhost", "rixx@localhost")]
if ADMINS:
    LOGGING["handlers"]["mail_admins"] = {
        "level": email_level,
        "class": "pretalx.common.exceptions.PretalxAdminEmailHandler",
    }
    LOGGING["loggers"]["django.request"]["handlers"].append("mail_admins")


## EMAIL SETTINGS
MAIL_FROM = SERVER_EMAIL = DEFAULT_FROM_EMAIL = config.get("mail", "from")
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_HOST = config.get("mail", "host")
    EMAIL_PORT = config.get("mail", "port")
    EMAIL_HOST_USER = config.get("mail", "user")
    EMAIL_HOST_PASSWORD = config.get("mail", "password")
    EMAIL_USE_TLS = config.getboolean("mail", "tls")
    EMAIL_USE_SSL = config.getboolean("mail", "ssl")


## CACHE SETTINGS
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
REAL_CACHE_USED = False
SESSION_ENGINE = None

HAS_MEMCACHED = bool(os.getenv("PRETALX_MEMCACHE", ""))
if HAS_MEMCACHED:
    REAL_CACHE_USED = True
    CACHES["default"] = {
        "BACKEND": "django.core.cache.backends.memcached.PyLibMCCache",
        "LOCATION": os.getenv("PRETALX_MEMCACHE"),
    }

HAS_REDIS = config.get("redis", "location") != "False"
if HAS_REDIS:
    CACHES["redis"] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config.get("redis", "location"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
    CACHES["redis_sessions"] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config.get("redis", "location"),
        "TIMEOUT": 3600 * 24 * 30,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
    if not HAS_MEMCACHED:
        CACHES["default"] = CACHES["redis"]
        REAL_CACHE_USED = True

    if config.getboolean("redis", "session"):
        SESSION_ENGINE = "django.contrib.sessions.backends.cache"
        SESSION_CACHE_ALIAS = "redis_sessions"

if not SESSION_ENGINE:
    if REAL_CACHE_USED:
        SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
    else:
        SESSION_ENGINE = "django.contrib.sessions.backends.db"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
MESSAGE_TAGS = {
    messages.INFO: "info",
    messages.ERROR: "danger",
    messages.WARNING: "warning",
    messages.SUCCESS: "success",
}


## I18N SETTINGS
USE_I18N = True
USE_L10N = True
USE_TZ = True
TIME_ZONE = config.get("locale", "time_zone")
LOCALE_PATHS = (Path(__file__).resolve().parent / "locale",)
FORMAT_MODULE_PATH = ["pretalx.common.formats"]

LANGUAGE_CODE = config.get("locale", "language_code")
LANGUAGES_INFORMATION = {
    "en": {
        "name": _("English"),
        "natural_name": "English",
        "official": True,
        "percentage": 100,
    },
    "de": {
        "name": _("German"),
        "natural_name": "Deutsch",
        "official": True,
        "percentage": 100,
    },
    "de-formal": {
        "name": _("German (formal)"),
        "natural_name": "Deutsch",
        "official": True,
        "percentage": 100,
        "public_code": "de",
    },
    "fr": {
        "name": _("French"),
        "natural_name": "Français",
        "official": False,
        "percentage": 98,
    },
    "zh-tw": {
        "name": _("Traditional Chinese (Taiwan)"),
        "natural_name": "Traditional Chinese (Taiwan)",
        "official": False,
        "percentage": 81,
    },
}
for code, language in LANGUAGES_INFORMATION.items():
    language["code"] = code

LANGUAGES = [
    (language["code"], language["name"]) for language in LANGUAGES_INFORMATION.values()
]


## AUTHENTICATION SETTINGS
AUTH_USER_MODEL = "person.User"
LOGIN_URL = "/orga/login"
AUTHENTICATION_BACKENDS = (
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
    "pretalx.common.auth.AuthenticationTokenBackend",
)
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


## MIDDLEWARE SETTINGS
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",  # Security first
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Next up: static files
    "django.middleware.common.CommonMiddleware",  # Set some sensible defaults, now, before responses are modified
    "pretalx.common.middleware.SessionMiddleware",  # Add session handling
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # Uses sessions
    "pretalx.common.auth.AuthenticationTokenMiddleware",  # Make auth tokens work
    "pretalx.common.middleware.MultiDomainMiddleware",  # Check which host is used and if it is valid
    "pretalx.common.middleware.EventPermissionMiddleware",  # Sets locales, request.event, available events, etc.
    "pretalx.common.middleware.CsrfViewMiddleware",  # Protect against CSRF attacks before forms/data are processed
    "django.contrib.messages.middleware.MessageMiddleware",  # Uses sessions
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # Protects against clickjacking
    "csp.middleware.CSPMiddleware",  # Modifies/sets CSP headers
]


## TEMPLATE AND STATICFILES SETTINGS
template_loaders = (
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
)
if not DEBUG:
    template_loaders = (("django.template.loaders.cached.Loader", template_loaders),)

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [DATA_DIR / "templates", BASE_DIR / "templates",],
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
                "pretalx.agenda.context_processors.is_html_export",
                "pretalx.common.context_processors.add_events",
                "pretalx.common.context_processors.locale_context",
                "pretalx.common.context_processors.messages",
                "pretalx.common.context_processors.system_information",
                "pretalx.orga.context_processors.orga_events",
            ],
            "loaders": template_loaders,
        },
    }
]

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
)
static_path = BASE_DIR / "pretalx" / "static"
STATICFILES_DIRS = [static_path] if static_path.exists() else []

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


## EXTERNAL APP SETTINGS
with suppress(ImportError):
    import django_extensions  # noqa

    INSTALLED_APPS.append("django_extensions")
with suppress(ImportError):
    import debug_toolbar  # noqa

    if DEBUG:
        INSTALLED_APPS.append("debug_toolbar.apps.DebugToolbarConfig")
        MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")
BOOTSTRAP4 = {
    "field_renderers": {
        "default": "bootstrap4.renderers.FieldRenderer",
        "inline": "bootstrap4.renderers.InlineFieldRenderer",
        "event": "pretalx.common.forms.renderers.EventFieldRenderer",
        "event-inline": "pretalx.common.forms.renderers.EventInlineFieldRenderer",
    }
}
DEBUG_TOOLBAR_PATCH_SETTINGS = False
DEBUG_TOOLBAR_CONFIG = {"JQUERY_URL": ""}
COMPRESS_ENABLED = COMPRESS_OFFLINE = not DEBUG
COMPRESS_PRECOMPILERS = (("text/x-scss", "django_libsass.SassCompiler"),)
COMPRESS_CSS_FILTERS = (
    # CssAbsoluteFilter is incredibly slow, especially when dealing with our _flags.scss
    # However, we don't need it if we consequently use the static() function in Sass
    # 'compressor.filters.css_default.CssAbsoluteFilter',
    "compressor.filters.cssmin.CSSCompressorFilter",
)

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": (
        "i18nfield.rest_framework.I18nJSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    'DEFAULT_PERMISSION_CLASSES': ('pretalx.api.permissions.ApiPermission',),
    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 25,
    "SEARCH_PARAM": "q",
    "ORDERING_PARAM": "o",
    "VERSIONING_PARAM": "v",
    "DATETIME_FORMAT": "iso-8601",
}
if DEBUG:
    REST_FRAMEWORK["COMPACT_JSON"] = False

WSGI_APPLICATION = "pretalx.wsgi.application"

PRETALX_VERSION = __version__
if DEBUG:
    with suppress(Exception):
        import subprocess

        PRETALX_VERSION = (
            subprocess.check_output(["/usr/bin/git", "describe", "--always"])
            .decode()
            .strip()
        )

with suppress(ImportError):
    from .override_settings import *  # noqa

log_initial(
    debug=DEBUG,
    config_files=CONFIG_FILES,
    db_name=db_name,
    db_backend=db_backend,
    LOG_DIR=LOG_DIR,
    plugins=PLUGINS,
)
