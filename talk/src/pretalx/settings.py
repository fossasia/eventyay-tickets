import logging
import os
import sys
from contextlib import suppress
from importlib.metadata import entry_points
from pathlib import Path
from urllib.parse import urlparse, urljoin

from django.contrib.messages import constants as messages
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from pretalx import __version__
from pretalx.common.settings.config import build_config
from pretalx.common.text.console import log_initial

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
    config.get(
        "filesystem",
        "static",
        fallback=BASE_DIR / "static.dist",
    )
)
IS_HTML_EXPORT = False
HTMLEXPORT_ROOT = Path(
    config.get(
        "filesystem",
        "htmlexport",
        fallback=DATA_DIR / "htmlexport",
    )
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
    "django.contrib.humanize",
    "django.contrib.sites",
]
EXTERNAL_APPS = [
    "compressor",
    "djangoformsetjs",
    "django_filters",
    "django_pdb",
    "jquery",
    "rest_framework.authtoken",
    "rules",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "oauth2_provider",
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
    "pretalx.eventyay_common",
]
FALLBACK_APPS = [
    "django.forms",
    "rest_framework",
    "drf_spectacular",
]
INSTALLED_APPS = DJANGO_APPS + EXTERNAL_APPS + LOCAL_APPS + FALLBACK_APPS

PLUGINS = []
for entry_point in entry_points(group="pretalx.plugin"):
    PLUGINS.append(entry_point.module)
    INSTALLED_APPS.append(entry_point.module)

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
BASE_PATH = config.get("site", "base_path", fallback="")
FORCE_SCRIPT_NAME = BASE_PATH
STATIC_URL = config.get("site", "static", fallback=BASE_PATH + "/static/")
MEDIA_URL = config.get("site", "media", fallback=BASE_PATH + "/media/")
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
FILE_UPLOAD_DEFAULT_LIMIT = int(config.get("files", "upload_limit")) * 1024 * 1024
IMAGE_DEFAULT_MAX_WIDTH = 1920
IMAGE_DEFAULT_MAX_HEIGHT = 1080
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000


## SECURITY SETTINGS
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"


def merge_csp(*options, config=None):
    result = list(options)
    if config:
        result += config.split(",")
    return tuple(result)


CSP_DEFAULT_SRC = merge_csp("'self'", config=config.get("site", "csp"))
CSP_SCRIPT_SRC = merge_csp("'self'", config=config.get("site", "csp_script"))
CSP_STYLE_SRC = merge_csp(
    "'self'", "'unsafe-inline'", config=config.get("site", "csp_style")
)
CSP_IMG_SRC = merge_csp("'self'", "data:", config=config.get("site", "csp_img"))
CSP_BASE_URI = ("'none'",)
CSP_FORM_ACTION = merge_csp("'self'", config=config.get("site", "csp_form"))

CSRF_COOKIE_NAME = "pretalx_csrftoken"
CSRF_TRUSTED_ORIGINS = [SITE_URL]
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False

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
        SECRET_KEY = SECRET_FILE.read_text()
    else:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
        SECRET_KEY = get_random_string(50, chars)
        with SECRET_FILE.open(mode="w") as f:
            SECRET_FILE.chmod(0o600)
            with suppress(Exception):  # chown is not available on all platforms
                os.chown(SECRET_FILE, os.getuid(), os.getgid())
            f.write(SECRET_KEY)

## TASK RUNNER SETTINGS
if bool(config.get("celery", "broker")):
    CELERY_BROKER_URL = config.get("celery", "broker")
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
    CELERY_RESULT_BACKEND = config.get("celery", "backend")
    CELERY_RESULT_BACKEND_THREAD_SAFE = True
    CELERY_TASK_ALWAYS_EAGER = False
else:
    CELERY_TASK_ALWAYS_EAGER = True

## DATABASE SETTINGS
db_backend = config.get("database", "backend")
db_name = config.get("database", "name", fallback=str(DATA_DIR / "db.sqlite3"))
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends." + db_backend,
        "NAME": db_name,
        "USER": config.get("database", "user"),
        "PASSWORD": config.get("database", "password"),
        "HOST": config.get("database", "host"),
        "PORT": config.get("database", "port"),
        "CONN_MAX_AGE": 0 if db_backend == "sqlite3" else 120,
        "CONN_HEALTH_CHECKS": db_backend != "sqlite3",
        "OPTIONS": (
            {"init_command": "PRAGMA synchronous=3; PRAGMA cache_size=2000;"}
            if db_backend == "sqlite3"
            else {}
        ),
        "TEST": {},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"


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
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        "": {"handlers": ["file", "console"], "level": loglevel, "propagate": True},
        "rules": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["file", "console"],
            "level": "ERROR",  # Otherwise, we log 404s at WARNING/whatever, which sucks
            "propagate": False,
        },
        "django.security": {
            "handlers": ["file", "console"],
            "level": loglevel,
            "propagate": True,
        },
        "django.security.DisallowedHost": {
            "handlers": ["null"],
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["file", "console"],
            "level": "INFO",  # Do not output all the queries
            "propagate": True,
        },
    },
}
logging.getLogger("MARKDOWN").setLevel(logging.WARNING)

email_level = config.get("logging", "email_level", fallback="ERROR") or "ERROR"
emails = config.get("logging", "email", fallback="").split(",")
DEFAULT_EXCEPTION_REPORTER = "pretalx.common.exceptions.PretalxExceptionReporter"
MANAGERS = ADMINS = [(email, email) for email in emails if email]
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
SESSION_ENGINE = None

HAS_REDIS = config.get("redis", "location") != "False"
if HAS_REDIS:
    CACHES["redis"] = {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config.get("redis", "location"),
    }
    CACHES["redis_sessions"] = {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config.get("redis", "location"),
        "TIMEOUT": 3600 * 24 * 30,
    }
    if config.getboolean("redis", "session"):
        SESSION_ENGINE = "django.contrib.sessions.backends.cache"
        SESSION_CACHE_ALIAS = "redis_sessions"

if not SESSION_ENGINE:
    if HAS_REDIS:
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
TIME_ZONE = config.get("locale", "time_zone")
LOCALE_PATHS = (Path(__file__).resolve().parent / "locale",)
FORMAT_MODULE_PATH = ["pretalx.common.formats"]

LANGUAGE_CODE = config.get("locale", "language_code")
LANGUAGE_COOKIE_NAME = "pretalx_language"
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
        "path": "de_DE",
    },
    "de-formal": {
        "name": _("German (formal)"),
        "natural_name": "Deutsch",
        "official": True,
        "percentage": 100,
        "public_code": "de",
        "path": "de_Formal",
    },
    "ar": {
        "name": _("Arabic"),
        "natural_name": "اَلْعَرَبِيَّةُ",
        "official": False,
        "percentage": 65,
    },
    "cs": {
        "name": _("Czech"),
        "natural_name": "Čeština",
        "official": False,
        "percentage": 87,
    },
    "el": {
        "name": _("Greek"),
        "natural_name": "Ελληνικά",
        "official": False,
        "percentage": 80,
    },
    "es": {
        "name": _("Spanish"),
        "natural_name": "Español",
        "official": False,
        "percentage": 71,
    },
    "fa-ir": {
        "name": _("Persian"),
        "natural_name": "قارسی",
        "official": False,
        "percentage": 99,
        "path": "fa_IR",
        "public_code": "fa_IR",
    },
    "fr": {
        "name": _("French"),
        "natural_name": "Français",
        "official": False,
        "percentage": 87,
        "path": "fr_FR",
    },
    "it": {
        "name": _("Italian"),
        "natural_name": "Italiano",
        "official": False,
        "percentage": 96,
    },
    "ja-jp": {
        "name": _("Japanese"),
        "natural_name": "日本語",
        "official": False,
        "percentage": 62,
        "public_code": "jp",
    },
    "nl": {
        "name": _("Dutch"),
        "natural_name": "Nederlands",
        "official": False,
        "percentage": 89,
    },
    "pl": {
        "name": _("Polish"),
        "natural_name": "Polski",
        "official": False,
        "percentage": 95,
    },
    "pt-br": {
        "name": _("Brasilian Portuguese"),
        "natural_name": "Português brasileiro",
        "official": False,
        "percentage": 99,
        "public_code": "pt",
    },
    "pt-pt": {
        "name": _("Portuguese"),
        "natural_name": "Português",
        "official": False,
        "percentage": 80,
        "public_code": "pt",
    },
    "ru": {
        "name": _("Russian"),
        "natural_name": "Русский",
        "official": True,
        "percentage": 0,
    },
    "sw": {
        "name": _("Swahili"),
        "natural_name": "Kiswahili",
        "official": False,
        "percentage": 0,
    },
    "ua": {
        "name": _("Ukrainian"),
        "natural_name": "Українська",
        "official": True,
        "percentage": 0,
    },
    "vi": {
        "name": _("Vietnamese"),
        "natural_name": "Tiếng Việt",
        "official": False,
        "percentage": 75,
    },
    "zh-hant": {
        "name": _("Traditional Chinese (Taiwan)"),
        "natural_name": "漢語",
        "official": False,
        "percentage": 59,
        "public_code": "zh",
    },
    "zh-hans": {
        "name": _("Simplified Chinese"),
        "natural_name": "简体中文",
        "official": False,
        "percentage": 76,
        "public_code": "zh",
    },
}
LANGUAGES_RTL = {
    "ar",
    "fa-ir",
}

for section in config.sections():
    # Plugins can add languages, which will not be visible
    # without the providing plugin being activated
    if section.startswith("language:"):
        language_code = section[len("language:") :]
        LANGUAGES_INFORMATION[language_code] = {
            "name": config.get(section, "name"),
            "public_code": config.get(section, "public_code", fallback=None)
            or language_code,
            "natural_name": config.get(section, "name"),
            "visible": False,
            "official": False,
            "percentage": None,
        }


for code, language in LANGUAGES_INFORMATION.items():
    language["code"] = code

LANGUAGES = [
    (language["code"], language["name"]) for language in LANGUAGES_INFORMATION.values()
]

# Only used in Python code. Changing this value will still leave most of the
# frontend using the default colour, but this makes sure that the backend
# uses one consistent value.
DEFAULT_EVENT_PRIMARY_COLOR = "#2185d0"

## AUTHENTICATION SETTINGS
AUTH_USER_MODEL = "person.User"
DEFAULT_AUTHENTICATION_BACKENDS = [
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
    "pretalx.common.auth.UserTokenAuthentication",
    "allauth.account.auth_backends.AuthenticationBackend",
]
EXTRA_AUTH_BACKENDS = [
    backend
    for backend in config.get(
        "authentication", "additional_auth_backends", fallback=""
    ).split(",")
    if backend
]
AUTHENTICATION_BACKENDS = DEFAULT_AUTHENTICATION_BACKENDS + EXTRA_AUTH_BACKENDS

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {
            "user_attributes": {"name", "email"},
        },
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]


## MIDDLEWARE SETTINGS
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",  # Security first
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Next up: static files
    "django.middleware.common.CommonMiddleware",  # Set some sensible defaults, now, before responses are modified
    "pretalx.common.middleware.SessionMiddleware",  # Add session handling
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # Uses sessions
    "csp.middleware.CSPMiddleware",  # Modifies/sets CSP headers
    "pretalx.common.middleware.MultiDomainMiddleware",  # Check which host is used and if it is valid
    "pretalx.common.middleware.EventPermissionMiddleware",  # Sets locales, request.event, available events, etc.
    "pretalx.common.middleware.CsrfViewMiddleware",  # Protect against CSRF attacks before forms/data are processed
    "django.contrib.messages.middleware.MessageMiddleware",  # Uses sessions
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # Protects against clickjacking
    "allauth.account.middleware.AccountMiddleware",  # Adds account information to the request
]


## TEMPLATE AND STATICFILES SETTINGS
template_loaders = (
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
)
if not DEBUG:
    template_loaders = (("django.template.loaders.cached.Loader", template_loaders),)

FORM_RENDERER = "pretalx.common.forms.renderers.TabularFormRenderer"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            DATA_DIR / "templates",
            BASE_DIR / "templates",
            BASE_DIR / "pretalx" / "templates",
        ],
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
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

# We have some Vue 3 frontend apps which are built with Vite, we need to
# tell Django to collect their compiled output files.
# Note that those apps must be built before running collectstatic.
FRONTEND_DIR = BASE_DIR / "pretalx" / "frontend"
# Note: We must assume that the directory exists,
# because when `collectstatic` was invoked by `rebuild` command,
# it only sees the settings before Vite runs.
STATICFILES_DIRS.append(FRONTEND_DIR / "global-nav-menu" / "dist")

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# We need this for Django to detect correctly that our website is served via HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

VITE_DEV_SERVER_PORT = 8080
VITE_DEV_SERVER = f"http://localhost:{VITE_DEV_SERVER_PORT}"
VITE_DEV_MODE = DEBUG
VITE_IGNORE = False  # Used to ignore `collectstatic`/`rebuild`


## EXTERNAL APP SETTINGS
with suppress(ImportError):
    from rich.traceback import install

    install(show_locals=True)

with suppress(ImportError):
    import django_extensions  # noqa

    INSTALLED_APPS.append("django_extensions")

if DEBUG:
    with suppress(ImportError):
        from debug_toolbar import settings as toolbar_settings  # noqa

        INTERNAL_IPS = ["127.0.0.1", "0.0.0.0", "::1"]
        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")
        DEBUG_TOOLBAR_PATCH_SETTINGS = False
        DEBUG_TOOLBAR_CONFIG = {
            "JQUERY_URL": "",
            "DISABLE_PANELS": toolbar_settings.PANELS_DEFAULTS,
        }
COMPRESS_ENABLED = COMPRESS_OFFLINE = not DEBUG
COMPRESS_PRECOMPILERS = (("text/x-scss", "django_libsass.SassCompiler"),)
COMPRESS_FILTERS = {
    "js": ["compressor.filters.jsmin.rJSMinFilter"],
    "css": (
        "compressor.filters.css_default.CssAbsoluteFilter",
        "compressor.filters.cssmin.rCSSMinFilter",
    ),
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("i18nfield.rest_framework.I18nJSONRenderer",),
    "DEFAULT_AUTHENTICATION_CLASSES": ("pretalx.common.auth.UserTokenAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("pretalx.api.permissions.ApiPermission",),
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser",),
    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "pretalx.api.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "SEARCH_PARAM": "q",
    "ORDERING_PARAM": "o",
    "DATETIME_FORMAT": "iso-8601",
    "EXCEPTION_HANDLER": "pretalx.api.exceptions.api_exception_handler",
}
if DEBUG:
    REST_FRAMEWORK["COMPACT_JSON"] = False

SPECTACULAR_SETTINGS = {
    "SCHEMA_PATH_PREFIX": "/api/events/{event}/",
    "SCHEMA_COERCE_PATH_PK_SUFFIX": True,
    "COMPONENT_SPLIT_PATCH": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": True,
    "AUTHENTICATION_WHITELIST": [],
    "ENABLE_DJANGO_DEPLOY_CHECK": False,
    "VERSION": None,
    "TITLE": "pretalx API",
    "SERVERS": [{"url": "https://pretalx.com"}],
    "EXTERNAL_DOCS": {"url": "https://docs.pretalx.org/api/"},
    "PATH_CONVERTER_OVERRIDES": {
        "slug": {"type": "string", "description": "The event’s slug"},
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "pretalx.api.documentation.postprocess_schema",
    ],
}
REST_FLEX_FIELDS = {
    "WILDCARD_VALUES": [],
    "RECURSIVE_EXPANSION_PERMITTED": False,
    "MAXIMUM_EXPANSION_DEPTH": 3,
}

WSGI_APPLICATION = "pretalx.wsgi.application"

PRETALX_VERSION = __version__
if DEBUG:
    with suppress(Exception):
        import subprocess

        PRETALX_VERSION = (
            subprocess.check_output(["/usr/bin/git", "describe", "--always", "--tags"])
            .decode()
            .strip()
        )

if "--no-pretalx-information" in sys.argv:
    sys.argv.remove("--no-pretalx-information")
else:
    log_initial()

EVENTYAY_TICKET_BASE_PATH = config.get(
    "urls", "eventyay-ticket", fallback="http://localhost/tickets/"
)
EVENTYAY_VIDEO_BASE_PATH = config.get(
    "urls", "eventyay-video", fallback="http://localhost/video/"
)

SITE_ID = 1
# for now, customer must verified their email at eventyay-ticket, so this check not required
ACCOUNT_EMAIL_VERIFICATION = "none"
# will take name from eventyay-ticket as username
ACCOUNT_USER_MODEL_USERNAME_FIELD = "name"
# redirect to home page after login with eventyay-ticket
LOGIN_REDIRECT_URL = BASE_PATH
# disable confirm step when using eventyay-ticket to login
# redirect_url as https
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# OAuth2 Client settings
OAUTH2_PROVIDER = {
    "AUTHORIZE_URL": urljoin(EVENTYAY_TICKET_BASE_PATH, "control/oauth2/authorize/"),
    "ACCESS_TOKEN_URL": urljoin(EVENTYAY_TICKET_BASE_PATH, "control/oauth2/token/"),
    "REDIRECT_URI": urljoin(SITE_URL, f'{BASE_PATH.strip("/")}/oauth2/callback/'),
    "SCOPE": ["profile"],
}
# Set default Application model if using default
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = "oauth2_provider.AccessToken"
OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = "oauth2_provider.RefreshToken"
OAUTH2_PROVIDER_AUTHORIZATION_CODE_MODEL = "oauth2_provider.AuthorizationCode"
OAUTH2_PROVIDER_CLIENT_MODEL = "oauth2_provider.Application"
OAUTH2_PROVIDER_ID_TOKEN_MODEL = "oauth2_provider.IDToken"
SSO_USER_INFO = urljoin(EVENTYAY_TICKET_BASE_PATH, "control/oauth2/user_info/")
# Disable this if you are not using HTTPS
OAUTHLIB_INSECURE_TRANSPORT = True

LOGOUT_REDIRECT_URL = "/"

CORS_ORIGIN_WHITELIST = [EVENTYAY_TICKET_BASE_PATH]
EVENTYAY_SSO_PROVIDER = "eventyay"

SILENCED_SYSTEM_CHECKS = [
    "security.W003",  # CsrfMiddleware modified but in use
    "security.W004",  # HSTS belongs to the proxy, not Django
    "security.W008",  # We have our own HTTPS check
    "security.W010",  # We have our own HTTPS check
    "security.W018",  # We have our own DEBUG check (to link our docs)
]

with suppress(ImportError):
    from .override_settings import *  # noqa
