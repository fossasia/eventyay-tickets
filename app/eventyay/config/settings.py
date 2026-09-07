import importlib.util
import os
import sys
from datetime import timedelta
from enum import StrEnum
from importlib.metadata import entry_points
from pathlib import Path
from typing import Annotated, cast
from urllib.parse import urlparse

import django.conf.locale
import importlib_metadata
from corsheaders.defaults import default_headers
from django.contrib.messages import constants as messages
from django.utils.translation import gettext_lazy as _
from kombu import Queue
from pycountry import currencies
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings as _BaseSettings
from pydantic_settings import PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from rich import print

from eventyay import __version__
from eventyay.consts import DEFAULT_PLUGINS, SizeKey


# To avoid loading unnecessary environment variables
# designated for other applications
# we only load those with EVY_ prefix.
_ENV_PREFIX = 'EVY_'

# Use this environment variable to choose the running environment.
# Example: EVY_RUNNING_ENVIRONMENT=production ./manage.py runserver
_ENV_KEY_ACTIVE_ENVIRONMENT = 'EVY_RUNNING_ENVIRONMENT'

# Our system will look for these TOML configuration files:
# - eventyay.{active_environment}.toml
# - eventyay.local.toml
#
# The 'eventyay.{active_environment}.toml' is the main configuration file
# for current active environment.
# The 'eventyay.local.toml' is optional, ignored by Git, for developers to override settings
# to match their personal setup.
# Sensitive data like passwords, API keys should be put in ".secrets/" directory,
# where the file names match the setting names, prefixed with "EVY_".
# For example, to provide `secret_key`, create a file named ".secrets/EVY_SECRET_KEY".
# Ref: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#secrets

_DEFAULT_DB_NAME = 'eventyay-db'

BASE_DIR = Path(__file__).resolve().parent.parent
# The root directory of the project, where "./manage.py" file is located.
PROJECT_ROOT = BASE_DIR.parent
SECRETS_DIR = PROJECT_ROOT / '.secrets'


# To choose the running environment, pass via EVY_RUNNING_ENVIRONMENT.
# For example:
#   EVY_RUNNING_ENVIRONMENT=production ./manage.py runserver
class RunningEnvironment(StrEnum):
    PRODUCTION = 'production'
    DEVELOPMENT = 'development'
    TESTING = 'testing'


active_environment = RunningEnvironment(os.getenv(_ENV_KEY_ACTIVE_ENVIRONMENT, 'development'))
# Some shortcuts. They are uppercase to allow usage outside this module (via django.conf.settings).
IS_DEVELOPMENT = active_environment == RunningEnvironment.DEVELOPMENT
IS_TESTING = active_environment == RunningEnvironment.TESTING
IS_PRODUCTION = active_environment == RunningEnvironment.PRODUCTION

DEFAULT_AUTH_BACKENDS = ('eventyay.base.auth.NativeAuthBackend',)


class BaseSettings(_BaseSettings):
    """
    Contains the settings which were loaded from the configuration file.

    After that, the settings will be manipulated to serve Django.
    This class is named "BaseSettings" because the settings it holds are not finalized yet.
    Doc: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

    Priority of settings sources (from highest to lowest):
    1. Secret files in ".secrets/" directory or Docker Secrets.
    2. Environment variables (with ``EVY_`` prefix).
    3. ".env" file in the current working directory.
    4. Local TOML configuration file (eventyay.local.toml).
    5. Environment-specific TOML configuration file (eventyay.{active_environment}.toml).
    """

    # Tell Pydantic how to load our configurations.
    model_config = SettingsConfigDict(
        env_prefix=_ENV_PREFIX,
        env_file='.env',
        env_file_encoding='utf-8',
        secrets_dir=SECRETS_DIR,
    )
    # Here, starting our settings fields.
    # The names follow what is in Django and converted to lowercase.
    debug: bool = False
    secret_key: str = 'please-give-one-in-secret-file'
    postgres_db: str = _DEFAULT_DB_NAME
    # When these values are `None`, "peer" connection method will be used.
    # We just need to have a PostgreSQL user with the same name as Linux user.
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_host: str | None = None
    postgres_port: int | None = None
    redis_url: str = 'redis://localhost/0'
    language_code: str = 'en'
    # Don't send emails to Internet by default.
    email_backend: str = 'django.core.mail.backends.console.EmailBackend'
    email_host: str = 'localhost'
    email_port: int = 587
    email_host_user: str = 'info@eventyay.com'
    email_host_password: str = ''
    email_use_tls: bool = True
    default_from_email: str = 'info@eventyay.com'
    allowed_hosts: list[str] = []
    # Used by "Talk" (pretalx). Not sure why it is named like this.
    core_modules: Annotated[tuple[str, ...], Field(default_factory=tuple)]
    # The MultiDomainMiddleware is depending on SITE_URL.
    # Override it to match the domain the website is running on,
    # or you will get "DisallowedHost" error.
    site_url: HttpUrl = 'http://localhost:8000'
    short_url: HttpUrl = 'http://localhost:8000'
    talk_hostname: str = 'http://localhost:8000'
    sentry_dsn: str = ''
    instance_name: str = 'eventyay'
    auth_backends: Annotated[tuple[str, ...], Field(default_factory=lambda: DEFAULT_AUTH_BACKENDS)]
    obligatory_2fa: bool = False
    plugins_default: Annotated[tuple[str, ...], Field(default_factory=lambda: DEFAULT_PLUGINS)]
    plugins_exclude: Annotated[tuple[str, ...], Field(default_factory=tuple)]
    metrics_enabled: bool = False
    metrics_user: str = 'metrics'
    metrics_passphrase: str = ''
    log_csp: bool = True
    csp_additional_header: str = ''
    celery_always_eager: bool = False
    # Being True will make Django-Compressor only look for pre-compiled files
    # and require us to run "compress" command after each frontend change.
    compress_offline_required: bool = False
    nanocdn_url: HttpUrl | None = None
    zoom_key: str = ''
    zoom_secret: str = ''
    control_secret: str = ''

    statsd_host: str = ''
    statsd_port: int = 8125
    statsd_prefix: str = 'eventyay'
    # Ask to provide comments when making changes in the admin interface.
    admin_audit_comments_asked: bool = False
    # To select a variant from CALL_FOR_SPEAKER_LOGIN_BTN_LABELS.
    call_for_speaker_login_button_label: str = 'default'
    # Set to 1 to enable Vite dev servers with HMR for live frontend development.
    npm_dev: bool = False
    fetch_ecb_rates: bool = True
    cache_tickets_hours: int = Field(default=24, ge=1)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[_BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Insert the TOML which matches the running environment
        toml_files = discover_toml_files()
        # We need `walk_up` because sometimes we stand in the "doc" directory.
        file_list_for_display = [str(p.relative_to(Path.cwd(), walk_up=True)) for p in toml_files]
        print(f'Loading configuration from: [blue]{file_list_for_display}[/]', file=sys.stderr)
        toml_settings = TomlConfigSettingsSource(
            settings_cls,
            toml_file=toml_files,
        )
        if Path('.env').is_file():
            print('Loading additional configuration from: [blue].env[/]', file=sys.stderr)
        if SECRETS_DIR.is_dir() and (files := tuple(SECRETS_DIR.glob(f'{_ENV_PREFIX}*'))):
            secrets_for_display = [str(p.relative_to(Path.cwd(), walk_up=True)) for p in files]
            print(f'Loading secrets from: [blue]{secrets_for_display}[/]', file=sys.stderr)
        return (
            file_secret_settings,
            # The following files will override values from TOML files.
            env_settings,
            # Though having TOML files, we still support .env file
            # because we need to share some settings with other tools.
            dotenv_settings,
            toml_settings,
        )

    # Upload size limit in MB, needs to to in accordance with SizeKey
    upload_size_csv: int = 10
    upload_size_image: int = 10
    upload_size_pdf: int = 10
    upload_size_xlsx: int = 2
    upload_size_attachment: int = 10
    upload_size_mail: int = 4
    upload_size_question: int = 20
    upload_size_other: int = 10
    response_size_webhook: int = 1


def discover_toml_files() -> list[Path]:
    """Discover TOML configuration files to be loaded.

    Where to search:
    - The same directory as this settings file.
    - In parent directories, go up until the base directory (containing manage.py).
    """
    toml_files: list[Path] = []
    current_dir = Path(__file__).resolve().parent
    names = [f'eventyay.{active_environment}.toml', 'eventyay.local.toml']
    while True:
        for name in names:
            candidate = current_dir / name
            if candidate.is_file():
                toml_files.append(candidate)
        if current_dir == PROJECT_ROOT:
            break
        current_dir = current_dir.parent
    # Sort the files so that the "local" file is loaded last,
    # and the one in the deepest directory is loaded first.
    toml_files.sort(key=lambda p: (1 if 'local' in p.name else 0, -len(p.parts)))
    return toml_files


def increase_redis_db(url: str, increment: int) -> str:
    """Increase the Redis database number in the given URL by the given increment.

    If the provided URL is missing DB number, we assume it is 0.
    """
    parsed = urlparse(url)
    try:
        db_number = int(parsed.path.lstrip('/')) + increment
    except ValueError:
        db_number = increment
    new_path = f'/{db_number}'
    new_url = parsed._replace(path=new_path).geturl()
    return new_url


conf = BaseSettings()

# --- Now, provide values to Django's settings. ---

# Note: DEBUG doesn't mean "development".
# Sometimes we need "debug" in production for troubleshooting,
# but please use with caution (it can reveal sensitive data like passwords, API keys).
DEBUG = conf.debug
SECRET_KEY = conf.secret_key
DATABASE_REPLICA = 'default'
FETCH_ECB_RATES = conf.fetch_ecb_rates
CACHE_TICKETS_MAX_AGE = timedelta(hours=conf.cache_tickets_hours)

DATA_DIR = BASE_DIR / 'data'
LOG_DIR = DATA_DIR / 'logs'
MEDIA_ROOT = DATA_DIR / 'media'
PROFILE_DIR = DATA_DIR / 'profiles'
# The compiled frontend files (from Vue3 apps) will be put here.
COMPILED_FRONTEND_DIR = DATA_DIR / 'compiled-frontend'

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
MEDIA_ROOT.mkdir(exist_ok=True)
COMPILED_FRONTEND_DIR.mkdir(exist_ok=True)


# Database configuration
DATABASES = {
    'default': {
        # We don't support other DB backends than PostgreSQL,
        # because we need advanced features like UUID, ARRAY, JSONB fields.
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': conf.postgres_db,
        # When these values are `None`, "peer" connection method will be used.
        # We just need to have a PostgreSQL user with the same name as Linux user.
        'USER': conf.postgres_user,
        'PASSWORD': conf.postgres_password,
        'HOST': conf.postgres_host,
        'PORT': conf.postgres_port,
        'CONN_MAX_AGE': 120,
    }
}

_LIBRARY_APPS = (
    'bootstrap3',
    'corsheaders',
    'channels',
    'compressor',
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.postgres',
    'django_filters',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'django_celery_beat',
    'django.forms',
    'djangoformsetjs',
    'jquery',
    'rest_framework.authtoken',
    'rules.apps.AutodiscoverRulesConfig',
    'oauth2_provider',
    'statici18n',
    'rest_framework',
    'drf_spectacular',
    # Provide styling for forms used by DRF API docs.
    'crispy_forms',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    'allauth.socialaccount.providers.mediawiki',
)

if DEBUG and importlib.util.find_spec('django_extensions'):
    _LIBRARY_APPS += ('django_extensions',)

if DEBUG and importlib.util.find_spec('debug_toolbar'):
    _LIBRARY_APPS += ('debug_toolbar',)

if DEBUG and importlib.util.find_spec('django_pdb'):
    _LIBRARY_APPS += ('django_pdb',)

_OURS_APPS = (
    'eventyay.agenda',
    'eventyay.common',
    'eventyay.orga',
    'eventyay.api',
    'eventyay.base',
    'eventyay.cfp',
    'eventyay.control.ControlConfig',
    'eventyay.event',
    'eventyay.eventyay_common',
    'eventyay.features.live.LiveConfig',
    'eventyay.features.analytics.graphs.GraphsConfig',
    'eventyay.features.importers.ImportersConfig',
    'eventyay.storage.StorageConfig',
    'eventyay.features.integrations.zoom.ZoomConfig',
    'eventyay.helpers',
    'eventyay.mail',
    'eventyay.multidomain',
    'eventyay.person',
    'eventyay.presale',
    'eventyay.plugins.socialauth',
    'eventyay.plugins.banktransfer',
    'eventyay.plugins.badges',
    'eventyay.plugins.sendmail',
    'eventyay.plugins.statistics',
    'eventyay.plugins.reports',
    'eventyay.plugins.checkinlists',
    'eventyay.plugins.manualpayment',
    'eventyay.plugins.scheduledtasks',
    'eventyay.plugins.ticketoutputpdf',
    'eventyay.schedule',
    'eventyay.submission',
)

EVENTYAY_PLUGINS_DEFAULT = conf.plugins_default
EVENTYAY_PLUGINS_EXCLUDE = conf.plugins_exclude

eps = importlib_metadata.entry_points()

# Ticket plugins (from legacy Pretix)
ticket_plugins = [ep.module for ep in eps.select(group='pretix.plugin') if ep.module not in EVENTYAY_PLUGINS_EXCLUDE]

# Talk plugins (from legacy Pretalx)
talk_plugins = [ep.module for ep in eps.select(group='pretalx.plugin') if ep.module not in EVENTYAY_PLUGINS_EXCLUDE]

SAFE_TICKET_PLUGINS = tuple(m for m in ticket_plugins if m not in {'pretix_pages'})

INSTALLED_APPS = _LIBRARY_APPS + SAFE_TICKET_PLUGINS + _OURS_APPS

# TODO: What is it for?
ALL_PLUGINS = sorted(ticket_plugins + talk_plugins)

# For "Talk" (pretalx).
# TODO: May rename, because it is extended from something, not only "core" modules.
CORE_MODULES = (
    INSTALLED_APPS
    + conf.core_modules
    + (
        'eventyay.base',
        'eventyay.presale',
        'eventyay.control',
        'eventyay.plugins.checkinlists',
        'eventyay.plugins.reports',
    )
)

# Widgets are public embeds served to any origin, so all origins must be allowed.
# CORS_URLS_REGEX restricts which URL paths receive the header — widget endpoints,
# event CSS, and /api/v1 (check-in app on access.eventyay.com or local Vite dev).
CORS_ALLOW_ALL_ORIGINS = True

CORS_URLS_REGEX = (
    r"^(?:"
    r".*/widget[s]?/.*|"
    r".*/schedule/widget/.*|"
    r".*/static/event\.css|"
    r".*/static/schedule/.*\.js|"
    r"/api/v1/.*"
    r")$"
)

CORS_ALLOW_HEADERS = [*default_headers, "exhibitor"]

# TODO: This list is only for display. It should not be here.
PLUGINS = []
for entry_point in entry_points(group='pretalx.plugin'):
    PLUGINS.append(entry_point.module)

# TODO: What is it for?
LOADED_PLUGINS = {}
for module_name in ALL_PLUGINS:
    try:
        module = importlib.import_module(module_name)
        LOADED_PLUGINS[module_name] = module
    except ModuleNotFoundError as e:
        print(f'Plugin not found: {module_name} ({e})')
    except ImportError as e:
        print(f'Failed to import plugin {module_name}: {e}')


AUTH_USER_MODEL = 'base.User'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

_LIBRARY_MIDDLEWARES = (
    'eventyay.api.middleware.PrivateNetworkAccessMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'eventyay.base.middleware.LoadSheddingMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'eventyay.middleware.block_404.Block404Middleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
)

if DEBUG and importlib.util.find_spec('debug_toolbar'):
    _LIBRARY_MIDDLEWARES += ('debug_toolbar.middleware.DebugToolbarMiddleware',)

_OURS_MIDDLEWARES = (
    'eventyay.base.middleware.CustomCommonMiddleware',
    'eventyay.base.middleware.GloballyDisabledPluginMiddleware',
    'eventyay.common.middleware.SessionMiddleware',  # Add session handling
    'eventyay.common.middleware.MultiDomainMiddleware',  # Check which host is used and if it is valid
    'eventyay.common.middleware.EventPermissionMiddleware',  # Sets locales, request.event, available events, etc.
    'eventyay.common.middleware.CsrfViewMiddleware',  # Protect against CSRF attacks before forms/data are processed
    'eventyay.multidomain.middlewares.MultiDomainMiddleware',
    'eventyay.multidomain.middlewares.SessionMiddleware',
    'eventyay.multidomain.middlewares.CsrfViewMiddleware',
    'eventyay.control.middleware.PermissionMiddleware',
    'eventyay.control.middleware.AuditLogMiddleware',
    'eventyay.control.video.middleware.SessionMiddleware',
    'eventyay.control.video.middleware.AuthenticationMiddleware',
    'eventyay.control.video.middleware.MessageMiddleware',
    'eventyay.base.middleware.LocaleMiddleware',
    'eventyay.base.middleware.SecurityMiddleware',
    'eventyay.presale.middleware.EventMiddleware',
    'oauth2_provider.middleware.OAuth2TokenMiddleware',
    'eventyay.api.middleware.ApiScopeMiddleware',
)

MIDDLEWARE = _LIBRARY_MIDDLEWARES + _OURS_MIDDLEWARES


_CORE_TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

template_loaders = (
    (('django.template.loaders.cached.Loader', _CORE_TEMPLATE_LOADERS),) if IS_PRODUCTION else _CORE_TEMPLATE_LOADERS
)

TEMPLATES = (
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': (DATA_DIR / 'templates',),
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.request',
                'django.template.context_processors.tz',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'eventyay.agenda.context_processors.is_html_export',
                'eventyay.common.context_processors.add_events',
                'eventyay.common.context_processors.locale_context',
                'eventyay.common.context_processors.messages',
                'eventyay.common.context_processors.system_information',
                'eventyay.orga.context_processors.orga_events',
                'eventyay.base.context.contextprocessor',
                'eventyay.control.context.contextprocessor',
                'eventyay.presale.context.contextprocessor',
                'eventyay.eventyay_common.context.contextprocessor',
                'django.template.context_processors.request',
            ],
            'loaders': template_loaders,
            'builtins': ['eventyay.presale.templatetags.presale_locale'],
        },
    },
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': [
            BASE_DIR / 'jinja-templates',
        ],
        'OPTIONS': {
            'environment': 'eventyay.jinja.environment',
            'extensions': (
                'jinja2.ext.i18n',
                'jinja2.ext.do',
                'jinja2.ext.debug',
                'jinja2.ext.loopcontrols',
            ),
        },
    },
)

# See: https://django-allauth.readthedocs.io/en/latest/configuration.html
AUTHENTICATION_BACKENDS = (
    'rules.permissions.ObjectPermissionBackend',
    'django.contrib.auth.backends.ModelBackend',
    # To support multiple email addresses per user, we use django-allauth's authentication backend.
    'allauth.account.auth_backends.AuthenticationBackend',
)

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = (
    # In development, we don't need strong password validation.
    ()
    if IS_DEVELOPMENT
    else (
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
    )
)

LANGUAGE_CODE = conf.language_code
# Due to an issue of drifting time in Celery, we don't allow to change TIME_ZONE yet.
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LOCALE_PATHS = (BASE_DIR / 'locale',)
FORMAT_MODULE_PATH = ['eventyay.helpers.formats']

# TODO: Move to consts.py
# Unified language configuration - single source of truth for all language information
_LANGUAGES_CONFIG = {
    'en': {
        'name': _('English'),
        'natural_name': 'English',
        'bidi': False,
        'official': True,
        'percentage': 100,
        'incubating': False,
    },
    'en-us': {
        'name': _('English (United States)'),
        'natural_name': 'English (United States)',
        'bidi': False,
        'official': True,
        'percentage': 100,
        'public_code': 'en',
        'incubating': False,
    },
    'en-gb': {
        'name': _('English (United Kingdom)'),
        'natural_name': 'English (United Kingdom)',
        'bidi': False,
        'official': True,
        'percentage': 100,
        'public_code': 'en',
        'incubating': False,
    },
    'en-au': {
        'name': _('English (Australia)'),
        'natural_name': 'English (Australia)',
        'bidi': False,
        'official': True,
        'percentage': 100,
        'public_code': 'en',
        'incubating': False,
    },
    'en-ca': {
        'name': _('English (Canada)'),
        'natural_name': 'English (Canada)',
        'bidi': False,
        'official': True,
        'percentage': 100,
        'public_code': 'en',
        'incubating': False,
    },
    'de': {
        'name': _('German'),
        'natural_name': 'Deutsch',
        'bidi': False,
        'official': True,
        'percentage': 100,
        'incubating': False,
    },
    'de-formal': {
        'name': _('German (formal)'),
        'natural_name': 'Deutsch',
        'bidi': False,
        'official': True,
        'percentage': 100,
        'public_code': 'de',
        'incubating': False,
    },
    'ar': {
        'name': _('Arabic'),
        'natural_name': 'اَلْعَرَبِيَّةُ',
        'bidi': True,
        'official': False,
        'percentage': 72,
        'incubating': False,
    },
    'bg': {
        'name': _('Bulgarian'),
        'natural_name': 'Български',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'bn': {
        'name': _('Bengali'),
        'natural_name': 'বাংলা',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'ca': {
        'name': _('Catalan'),
        'natural_name': 'Català',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'cs': {
        'name': _('Czech'),
        'natural_name': 'Čeština',
        'bidi': False,
        'official': False,
        'percentage': 97,
        'incubating': False,
    },
    'da': {
        'name': _('Danish'),
        'natural_name': 'Dansk',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'el': {
        'name': _('Greek'),
        'natural_name': 'Ελληνικά',
        'bidi': False,
        'official': False,
        'percentage': 90,
        'incubating': False,
    },
    'es': {
        'name': _('Spanish'),
        'natural_name': 'Español',
        'bidi': False,
        'official': False,
        'percentage': 80,
        'incubating': False,
    },
    'fa-ir': {
        'name': _('Persian'),
        'natural_name': 'قارسی',
        'bidi': True,
        'official': False,
        'percentage': 99,
        'public_code': 'fa_IR',
        'incubating': False,
    },
    'fi': {
        'name': _('Finnish'),
        'natural_name': 'Suomi',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': True,
    },
    'fr': {
        'name': _('French'),
        'natural_name': 'Français',
        'bidi': False,
        'official': False,
        'percentage': 98,
        'incubating': False,
    },
    'hu': {
        'name': _('Hungarian'),
        'natural_name': 'Magyar',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'hi': {
        'name': _('Hindi'),
        'natural_name': 'हिन्दी',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'gu': {
        'name': _('Gujarati'),
        'natural_name': 'ગુજરાતી',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'id': {
        'name': _('Indonesian'),
        'natural_name': 'Bahasa Indonesia',
        'bidi': False,
        'official': False,
        'percentage': 90,
        'incubating': False,
    },
    'it': {
        'name': _('Italian'),
        'natural_name': 'Italiano',
        'bidi': False,
        'official': False,
        'percentage': 95,
        'incubating': False,
    },
    'ja-jp': {
        'name': _('Japanese'),
        'natural_name': '日本語',
        'bidi': False,
        'official': False,
        'percentage': 69,
        'public_code': 'jp',
        'incubating': False,
    },
    'ko': {
        'name': _('Korean'),
        'natural_name': '한국어',
        'bidi': False,
        'official': False,
        'percentage': 88,
        'incubating': False,
    },
    'km': {
        'name': _('Khmer'),
        'natural_name': 'ខ្មែរ',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'lv': {
        'name': _('Latvian'),
        'natural_name': 'Latviešu',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'ms': {
        'name': _('Malay'),
        'natural_name': 'Bahasa Melayu',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'ml': {
        'name': _('Malayalam'),
        'natural_name': 'മലയാളം',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'mr': {
        'name': _('Marathi'),
        'natural_name': 'मराठी',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'nb-no': {
        'name': _('Norwegian Bokmål'),
        'natural_name': 'Norsk bokmål',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'nl': {
        'name': _('Dutch'),
        'natural_name': 'Nederlands',
        'bidi': False,
        'official': False,
        'percentage': 88,
        'incubating': False,
    },
    'nl-informal': {
        'name': _('Dutch (informal)'),
        'natural_name': 'Nederlands',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'public_code': 'nl',
        'incubating': False,
    },
    'pl': {
        'name': _('Polish'),
        'natural_name': 'Polski',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': True,
    },
    'pl-informal': {
        'name': _('Polish (informal)'),
        'natural_name': 'Polski (nieformalny)',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'public_code': 'pl',
        'incubating': False,
    },
    'pt-br': {
        'name': _('Brazilian Portuguese'),
        'natural_name': 'Português brasileiro',
        'bidi': False,
        'official': False,
        'percentage': 89,
        'public_code': 'pt',
        'incubating': True,
    },
    'pt-pt': {
        'name': _('Portuguese'),
        'natural_name': 'Português',
        'bidi': False,
        'official': False,
        'percentage': 89,
        'public_code': 'pt',
        'incubating': False,
    },
    'ro': {
        'name': _('Romanian'),
        'natural_name': 'Română',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'ru': {
        'name': _('Russian'),
        'natural_name': 'Русский',
        'bidi': False,
        'official': True,
        'percentage': 0,
        'incubating': False,
    },
    'si': {
        'name': _('Sinhala'),
        'natural_name': 'සිංහල',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'sl': {
        'name': _('Slovenian'),
        'natural_name': 'Slovenščina',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'sv': {
        'name': _('Swedish'),
        'natural_name': 'Svenska',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'sw': {
        'name': _('Swahili'),
        'natural_name': 'Kiswahili',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'ta': {
        'name': _('Tamil'),
        'natural_name': 'தமிழ்',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'te': {
        'name': _('Telugu'),
        'natural_name': 'తెలుగు',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'th': {
        'name': _('Thai'),
        'natural_name': 'ไทย',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'tr': {
        'name': _('Turkish'),
        'natural_name': 'Türkçe',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'uk': {
        'name': _('Ukrainian'),
        'natural_name': 'Українська',
        'bidi': False,
        'official': True,
        'percentage': 0,
        'incubating': False,
    },
    'ur': {
        'name': _('Urdu'),
        'natural_name': 'اردو',
        'bidi': True,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'vi': {
        'name': _('Vietnamese'),
        'natural_name': 'Tiếng Việt',
        'bidi': False,
        'official': False,
        'percentage': 0,
        'incubating': False,
    },
    'zh-hans': {
        'name': _('Chinese Simplified'),
        'natural_name': '简体中文',
        'bidi': False,
        'official': False,
        'percentage': 86,
        'public_code': 'zh',
        'incubating': False,
    },
    'zh-hant': {
        'name': _('Chinese Traditional'),
        'natural_name': '繁體中文',
        'bidi': False,
        'official': False,
        'percentage': 66,
        'public_code': 'zh',
        'incubating': False,
    },
}

# Derive legacy variables from _LANGUAGES_CONFIG for backward compatibility
def _build_all_languages():
    result = []
    for code, info in _LANGUAGES_CONFIG.items():
        natural_name = info.get('natural_name', '')
        name_obj = info['name']
        english_name = name_obj._args[0] if hasattr(name_obj, '_args') and name_obj._args else natural_name
        if natural_name.strip().casefold() == english_name.strip().casefold():
            label = natural_name
        else:
            label = f'\u200e{natural_name} ({english_name})'
        result.append((code, label))
    return result


ALL_LANGUAGES = _build_all_languages()

LANGUAGES_OFFICIAL = {code for code, info in _LANGUAGES_CONFIG.items() if info.get('official', False)}
LANGUAGES_INCUBATING = {code for code, info in _LANGUAGES_CONFIG.items() if info.get('incubating', False)}
LANGUAGES_RTL = {code for code, info in _LANGUAGES_CONFIG.items() if info.get('bidi', False)}

# Override Django's LANGUAGES_BIDI so i18n form inputs always render dir="ltr".
# This keeps placeholders left-aligned for RTL languages while browsers still
# auto-detect RTL characters for typed content (Unicode bidi algorithm handles it).
LANGUAGES_BIDI = []

# TODO: Convert to tuple (some code still assumes LANGUAGES to be a list)
LANGUAGES = (
    [(k, v) for k, v in ALL_LANGUAGES if k not in LANGUAGES_INCUBATING] if IS_PRODUCTION else list(ALL_LANGUAGES)
)

# Build EXTRA_LANG_INFO for Django's locale system (only for languages that need special handling)
EXTRA_LANG_INFO = {
    code: {
        'bidi': info.get('bidi', False),
        'code': code,
        'name': info['name'],
        'name_local': info.get('natural_name', info['name']),
        'public_code': info.get('public_code', code),
    }
    for code, info in _LANGUAGES_CONFIG.items()
    if info.get('public_code') or code in ['de-formal', 'nl-informal', 'fr', 'lv', 'pt-pt', 'sw']
}

django.conf.locale.LANG_INFO.update(EXTRA_LANG_INFO)

# LANGUAGES_INFORMATION is an alias for _LANGUAGES_CONFIG
# This maintains backward compatibility with existing code
LANGUAGES_INFORMATION = _LANGUAGES_CONFIG

# Documentation imports Django modules through autodoc. Keep those imports
# deterministic: documentation builds must not require a live Redis service or
# a Celery broker just to render Python API pages.
DOCS_BUILD = os.getenv('EVY_DOCS_BUILD') == '1'

# Use Redis for caching in normal application environments. Sphinx uses local
# memory caches so importing forms and views does not contact external services.
REDIS_URL = conf.redis_url

CACHES = (
    {
        name: {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': f'eventyay-docs-{name}',
        }
        for name in ('default', 'process', 'redis')
    }
    if DOCS_BUILD
    else {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        },
        'process': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        },
        # TODO: Remove. Use the 'default' cache everywhere.
        'redis': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'REDIS_CLIENT_KWARGS': {'health_check_interval': 30},
            },
        },
    }
)

# Use Redis for session storage
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# TODO: Remove. Redis is always required.
HAS_REDIS = bool(REDIS_URL) and not DOCS_BUILD

# TODO: Remove. Always use Redis Pub/Sub for Channels.
REDIS_USE_PUBSUB = not DOCS_BUILD

HAS_CELERY = True
CELERY_BROKER_URL = 'memory://' if DOCS_BUILD else increase_redis_db(REDIS_URL, 1)
CELERY_RESULT_BACKEND = 'cache+memory://' if DOCS_BUILD else increase_redis_db(REDIS_URL, 2)
CELERY_TASK_ALWAYS_EAGER = True if DOCS_BUILD else conf.celery_always_eager
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_QUEUES = (
    Queue('default', routing_key='default.#'),
    Queue('longrunning', routing_key='longrunning.#'),
    Queue('background', routing_key='background.#'),
    Queue('notifications', routing_key='notifications.#'),
)
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SCHEDULE = {
    'eventyay-periodic-task-signal': {
        'task': 'eventyay.common.tasks.send_periodic_signal',
        'schedule': 60.0,
    },
}
CELERY_TASK_TRACK_STARTED = True
# Keep Django/eventyay logging configuration in workers and avoid redirecting stdout/stderr.
# This ensures logger output remains visible as configured and is not swallowed by Celery.
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_REDIRECT_STDOUTS = False
CELERY_TASK_ROUTES = {
    'eventyay.base.services.notifications.*': {'queue': 'notifications'},
    'eventyay.api.webhooks.*': {'queue': 'notifications'},
    'eventyay.plugins.badges.tasks.*': {'queue': 'longrunning'},
    'eventyay.base.services.export.*': {'queue': 'longrunning'},
    'eventyay.base.services.orderimport.*': {'queue': 'longrunning'},
    'eventyay.features.importers.tasks.*': {'queue': 'longrunning'},
    'eventyay.base.services.tickets.generate': {'queue': 'longrunning'},
    'eventyay.base.services.tickets.invalidate_cache': {'queue': 'longrunning'},
    # Registered name in eventyay.agenda.tasks (legacy pretalx namespace).
    'pretalx.agenda.export_schedule_html': {'queue': 'longrunning'},
}

# The folder where static files are collected to. It is shared with Nginx.
STATIC_ROOT = BASE_DIR / 'static.dist'
# These are the sources of `collectstatic` command.
STATICFILES_DIRS = (
    # Added to make sure root package static assets (e.g. pretixcontrol/scss/) are found
    (BASE_DIR / 'static'),
    COMPILED_FRONTEND_DIR,
)
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

CRISPY_TEMPLATE_PACK = 'bootstrap4'

NANOCDN_URL = conf.nanocdn_url
# To make our app stable first, we won't use NanoCDN for now.
default_storage_backend = 'django.core.files.storage.FileSystemStorage'

STORAGES = {
    'default': {'BACKEND': default_storage_backend},
    # To make our app stable first, we won't use ManifestStaticFilesStorage for now.
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

# For django-statici18n
STATICI18N_ROOT = BASE_DIR / 'static'

FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o775
FILE_UPLOAD_PERMISSIONS = 0o644

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
    ('text/vue', 'eventyay.helpers.compressor.VueCompiler'),
    # This is to help Django-Compressor minify 'module' type JS files.
    # The actual job is done by esbuild. In the JS code, we can use "import" statements,
    # but only with relative import paths (like `import Alpine from '../alpinejs.mjs'`).
    # We don't need to specify {outfile} because both esbuild and Django-Compressor support stdin/stdout.
    # We still specify {infile} to enable resolving "import" paths.
    ('module', 'npx esbuild {infile} --bundle --minify --platform=browser'),
)
# We have one Vue 2 app to be built by Django-Compressor, so we need to enable compression.
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = conf.compress_offline_required
COMPRESS_CSS_FILTERS = (
    # CssAbsoluteFilter is incredibly slow, especially when dealing with our _flags.scss
    # However, we don't need it if we consequently use the static() function in Sass
    # 'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSCompressorFilter',
)

# Security settings
X_FRAME_OPTIONS = 'DENY'
# Video-Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
CSP_DEFAULT_SRC = ("'self'", "'unsafe-eval'")
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# URL settings
ROOT_URLCONF = 'eventyay.multidomain.maindomain_urlconf'

INTERNAL_IPS = ('127.0.0.1', '::1')
ALLOWED_HOSTS = conf.allowed_hosts

EMAIL_BACKEND = conf.email_backend
# Only effective when using 'django.core.mail.backends.filebased.EmailBackend' (default in development)
EMAIL_FILE_PATH = DATA_DIR / 'dev-sent-emails'
EMAIL_HOST = conf.email_host
EMAIL_PORT = conf.email_port
EMAIL_HOST_USER = conf.email_host_user
EMAIL_HOST_PASSWORD = conf.email_host_password
EMAIL_USE_TLS = conf.email_use_tls
# Ref: https://docs.djangoproject.com/en/5.2/ref/settings/#email-use-ssl
EMAIL_USE_SSL = not conf.email_use_tls
SERVER_EMAIL = DEFAULT_FROM_EMAIL = conf.default_from_email

# TODO: Remove (why we need to use different values from default?)
SESSION_COOKIE_NAME = 'eventyay_session'
LANGUAGE_COOKIE_NAME = 'eventyay_language'
CSRF_COOKIE_NAME = 'eventyay_csrftoken'
# TODO: After merging eventyay-xxx componenents, we may not need this.
CSRF_TRUSTED_ORIGINS = ['http://localhost:1337', 'http://next.eventyay.com:1337', 'https://next.eventyay.com']
SESSION_COOKIE_HTTPONLY = True
# TODO: Remove. We always use Nginx or we are even behind CloudFlare,
# so trusting X-Forwarded-For is a must, if we want to get real client IP.
TRUST_X_FORWARDED_FOR = True

WSGI_APPLICATION = 'eventyay.config.wsgi.application'
ASGI_APPLICATION = 'eventyay.config.asgi.application'

_LOGGING_HANDLERS = {
    'console': {
        'level': 'DEBUG',
        'class': 'logging.StreamHandler',
        'formatter': 'verbose',
    },
    'rich': {
        'level': 'DEBUG',
        'class': 'rich.logging.RichHandler' if os.getenv('TERM') else 'logging.StreamHandler',
        'formatter': 'tiny' if os.getenv('TERM') else 'verbose',
    },
}
_LOGGING_FORMATTERS = {
    'verbose': {'format': '%(levelname)s %(asctime)s %(module)s: %(message)s'},
    'tiny': {
        'format': '%(message)s',
        'datefmt': '[%X]',
    },
}
_adaptive_console_handler = 'rich' if DEBUG else 'console'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'root': {
        'level': 'WARNING',
        'handlers': [_adaptive_console_handler],
    },
    'formatters': _LOGGING_FORMATTERS,
    'filters': {
        'one_line_warning': {'()': 'eventyay.helpers.security.OneLineWarningFilter'},
    },
    'handlers': _LOGGING_HANDLERS,
    'loggers': {
        'django.db.backends': {
            'handlers': [_adaptive_console_handler],
            'level': 'WARNING',
            'propagate': False,
        },
        # Daphne always print color codes, so we bypass rich handler
        'django.channels.server': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False,
        },
        'rules': {
            'handlers': [_adaptive_console_handler],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'eventyay': {
            'handlers': [_adaptive_console_handler],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'django.security.DisallowedHost': {
            'handlers': [_adaptive_console_handler],
            'filters': ['one_line_warning'],
            'propagate': False,
        },
    },
}

# NOTE: I skipped configuring sending errors via emails to developers.
# We should setup Sentry for error tracking later.

# --- Django allauth settings for social login ---

# NOTE: django-allauth changed some settings name. Check https://docs.allauth.org/en/dev/release-notes/recent.html
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# 'mandatory' means allauth's own login view (/accounts/login/) will block unverified users.
# Existing users who registered before email verification was enforced may be affected if they
# use that URL. Our custom login view (auth.login) does not enforce this,
# so those users remain unaffected. After signup, allauth redirects to
# account_email_verification_sent (not to the login page), so ACCOUNT_SIGNUP_REDIRECT_URL
# below is only reached when the user is already verified (e.g. social auth signup).
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
# Prefer Jinja2 templates for django-allauth
ACCOUNT_TEMPLATE_EXTENSION = 'jinja'
ACCOUNT_ADAPTER = 'eventyay.eventyay_common.adapter.CustomAccountAdapter'
ACCOUNT_SIGNUP_REDIRECT_URL = 'auth.login'
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = '/common/account/email'

SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_ADAPTER = 'eventyay.plugins.socialauth.adapter.CustomSocialAccountAdapter'
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True

SOCIALACCOUNT_PROVIDERS = {
    'mediawiki': {
        # VERIFIED_EMAIL=True trusts the email even when confirmed_email=False.
        # No custom SCOPE — WikiMedia's default scope returns the full profile.
        # Email may be null if the OAuth consumer lacks "View email" permission;
        # the username fallback in CustomSocialAccountAdapter handles that case.
        'VERIFIED_EMAIL': True,
        'provider_class': 'eventyay.plugins.socialauth.mediawiki_provider.EventyayMediaWikiProvider',
    },
}

OAUTH2_PROVIDER_APPLICATION_MODEL = 'api.OAuthApplication'
OAUTH2_PROVIDER_GRANT_MODEL = 'api.OAuthGrant'
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = 'api.OAuthAccessToken'
OAUTH2_PROVIDER_ID_TOKEN_MODEL = 'api.OAuthIDToken'
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = 'api.OAuthRefreshToken'
OAUTH2_PROVIDER = {
    'SCOPES': {
        'profile': _('User profile only'),
        'read': _('Read access'),
        'write': _('Write access'),
    },
    'OAUTH2_VALIDATOR_CLASS': 'eventyay.api.oauth.Validator',
    'ALLOWED_REDIRECT_URI_SCHEMES': ['https'] if IS_PRODUCTION else ['http', 'https'],
    'ACCESS_TOKEN_EXPIRE_SECONDS': 3600 * 24,
    'ROTATE_REFRESH_TOKEN': False,
    'PKCE_REQUIRED': False,
    'OIDC_RESPONSE_TYPES_SUPPORTED': ['code'],  # We don't support proper OIDC for now
}

# Channels (WebSocket) configuration
redis_connection_kwargs = {
    'retry': Retry(ExponentialBackoff(), 3),
    'health_check_interval': 30,
}
redis_hosts = [
    {
        'address': REDIS_URL,
        **redis_connection_kwargs,
    }
]
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': ('channels_redis.pubsub.RedisPubSubChannelLayer'),
        'CONFIG': {
            'hosts': redis_hosts,
            'prefix': 'eventyay:asgi:',
            'capacity': 10000,
        },
    },
}

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'eventyay.api.auth.permission.EventPermission',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'PAGE_SIZE': 50,
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'eventyay.api.auth.device.DeviceTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'eventyay.api.auth.token.TeamTokenAuthentication',
        'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
    ),
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'UNICODE_JSON': False,
    # User throttle is global (keyed by user/token, NAT-safe). Anonymous IP throttling
    # is opt-in on high-traffic public endpoints only (streams, schedule).
    'DEFAULT_THROTTLE_CLASSES': [
        'eventyay.api.throttles.EventyayUserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '300/minute',
        'public_stream': '10/minute',
        'public_schedule': '30/minute',
    },
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'eventyay API',
    'DESCRIPTION': 'API for managing eventyay organizers and events.',
    'VERSION': 'v1',
    'DEFAULT_GENERATOR_CLASS': 'eventyay.api.schema.EventyaySchemaGenerator',
    'SCHEMA_PATH_PREFIX': r'/api/v1',
    'SERVE_INCLUDE_SCHEMA': False,
    'PREPROCESSING_HOOKS': [
        'eventyay.api.documentation.exclude_unmigrated_plugin_endpoints',
    ],
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
        'eventyay.api.documentation.postprocess_schema',
    ],
}

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
# TODO: Remove. This is an empty string used in URL construction. Needs careful evaluation before removal.
BASE_PATH = ''

SITE_URL = str(conf.site_url)
SITE_NETLOC = urlparse(SITE_URL).netloc

LOGIN_URL = 'auth.login'
LOGIN_URL_CONTROL = 'auth.login'

# TODO: We should not need them (after merging eventyay-xxx components).
VIDEO_BASE_PATH = '/video'
WEBSOCKET_URL = '/ws/event/'
TALK_BASE_PATH = ''
LOGIN_REDIRECT_URL = '/common/account/general'

FILE_UPLOAD_DEFAULT_LIMIT = 10 * 1024 * 1024
IMAGE_SVG_MAX_SIZE = 1 * 1024 * 1024
IMAGE_DEFAULT_MAX_WIDTH = 1920
IMAGE_DEFAULT_MAX_HEIGHT = 1080
IMAGE_BACKFILL_MIN_SIZE_KB = 500

BYTES_IN_MB = 1024 * 1024

# Config for max size limits
MAX_SIZE_CONFIG = {key: BYTES_IN_MB * cast(int, getattr(conf, key)) for key in SizeKey}

FORM_RENDERER = 'eventyay.common.forms.renderers.TabularFormRenderer'

# TODO: Move to consts.py. It should not be dynamic, or it will cause generating DB migrations.
DEFAULT_CURRENCY = 'USD'
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
CURRENCIES = list(currencies)


HTMLEXPORT_ROOT = DATA_DIR / 'htmlexport'
HTMLEXPORT_ROOT.mkdir(exist_ok=True)

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
MESSAGE_TAGS = {
    messages.INFO: 'alert-info',
    messages.ERROR: 'alert-danger',
    messages.WARNING: 'alert-warning',
    messages.SUCCESS: 'alert-success',
}
BOOTSTRAP3 = {
    'success_css_class': '',
    'field_renderers': {
        'default': 'bootstrap3.renderers.FieldRenderer',
        'inline': 'bootstrap3.renderers.InlineFieldRenderer',
        'control': 'eventyay.control.forms.renderers.ControlFieldRenderer',
        'bulkedit': 'eventyay.control.forms.renderers.BulkEditFieldRenderer',
        'bulkedit_inline': 'eventyay.control.forms.renderers.InlineBulkEditFieldRenderer',
        'checkout': 'eventyay.presale.forms.renderers.CheckoutFieldRenderer',
    },
}

# TODO: The value is an URL (https://...) but the name is "hostname". Rename it.
# Also, after merging eventyay-xxx components, we may not need this.
TALK_HOSTNAME = conf.talk_hostname

# TODO: Remove, why we have to get this information from settings?
EVENTYAY_VERSION = __version__

# TODO: Remove.
# These values are used for channel layer group name. Why we need to name group with Git commit?
EVENTYAY_COMMIT = os.getenv('EVENTYAY_COMMIT_SHA', 'unknown')
EVENTYAY_ENVIRONMENT = os.getenv('EVENTYAY_ENVIRONMENT', 'unknown')

# Sentry configuration
SENTRY_DSN = conf.sentry_dsn
SENTRY_ENABLED = bool(SENTRY_DSN)
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    from django.core.exceptions import PermissionDenied
    from django.http import Http404

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[CeleryIntegration(), DjangoIntegration()],
        send_default_pii=False,
        debug=DEBUG,
        release=EVENTYAY_COMMIT if EVENTYAY_COMMIT != 'unknown' else None,
        environment=active_environment.value,
        ignore_errors=[Http404, PermissionDenied],
    )

# Multifactor authentication configuration
MULTIFACTOR = {
    'LOGIN_CALLBACK': False,
    'RECHECK': True,
    'RECHECK_MIN': 3600 * 24,
    'RECHECK_MAX': 3600 * 24 * 7,
    'FIDO_SERVER_ID': urlparse(SITE_URL).hostname,
    'FIDO_SERVER_NAME': 'Eventyay',
    'TOKEN_ISSUER_NAME': 'Eventyay',
    'U2F_APPID': SITE_URL,
    'FACTORS': ['FIDO2'],
    'FALLBACKS': {},
}

INSTANCE_NAME = conf.instance_name
EVENTYAY_REGISTRATION = True
EVENTYAY_PASSWORD_RESET = True
EVENTYAY_LONG_SESSIONS = True
# Ref: https://docs.pretix.eu/dev/development/api/auth.html
EVENTYAY_AUTH_BACKENDS = conf.auth_backends
EVENTYAY_ADMIN_AUDIT_COMMENTS = conf.admin_audit_comments_asked
EVENTYAY_OBLIGATORY_2FA = conf.obligatory_2fa
EVENTYAY_SESSION_TIMEOUT_RELATIVE = 3600 * 3
EVENTYAY_SESSION_TIMEOUT_ABSOLUTE = 3600 * 12

# TODO: The `pdftk` tool should be auto-detected.
PDFTK = ''

# Disable the feature for now.
PROFILING_RATE = 0

METRICS_ENABLED = conf.metrics_enabled
METRICS_USER = conf.metrics_user
METRICS_PASSPHRASE = conf.metrics_passphrase

LOG_CSP = conf.log_csp
CSP_ADDITIONAL_HEADER = conf.csp_additional_header

SHORT_URL = str(conf.short_url)
# TODO: Remove. Our views should calculate it from the current connected HTTP/HTTPS protocol,
# instead of relying on a setting.
WEBSOCKET_PROTOCOL = 'wss' if IS_PRODUCTION else 'ws'

ZOOM_KEY = conf.zoom_key
ZOOM_SECRET = conf.zoom_secret
CONTROL_SECRET = conf.control_secret
STATSD_HOST = conf.statsd_host
STATSD_PORT = conf.statsd_port
STATSD_PREFIX = conf.statsd_prefix

FRONTEND_DIR = BASE_DIR / 'webapp'
VITE_DEV_MODE = conf.npm_dev
VITE_DEV_SERVER_PORTS = {
    'schedule-editor': 'http://localhost:8080',
    'video': 'http://localhost:8880',
    'schedule': 'http://localhost:8082',
}

# Not sure if they need to be configurable.
ENTROPY = {
    'order_code': 5,
    'ticket_secret': 32,
    'voucher_code': 16,
    'giftcard_secret': 12,
}

IS_HTML_EXPORT = False
HTMLEXPORT_ROOT = DATA_DIR / 'htmlexport'

# TODO: Move to consts.py
EVENTYAY_PRIMARY_COLOR = '#2185d0'
DEFAULT_EVENT_PRIMARY_COLOR = '#2185d0'
PRETIX_PRIMARY_COLOR = EVENTYAY_PRIMARY_COLOR

IMAGE_DEFAULT_MAX_WIDTH = 2000
IMAGE_DEFAULT_MAX_HEIGHT = 2000

CALL_FOR_SPEAKER_LOGIN_BUTTON_LABEL = conf.call_for_speaker_login_button_label

if IS_DEVELOPMENT:
    # Support for Android emulators and port forwarding
    if '*' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS = list(dict.fromkeys([*ALLOWED_HOSTS, '10.0.2.2', '10.0.3.2']))
    # Trust standard local and emulator origins for CSRF
    CSRF_TRUSTED_ORIGINS += ['http://localhost:8000', 'http://127.0.0.1:8000', 'http://10.0.2.2:8000', 'http://10.0.3.2:8000']
