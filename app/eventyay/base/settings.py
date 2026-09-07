import datetime as dt
import json
import operator
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Model
from django.utils.translation import gettext_lazy as _
from hierarkey.models import GlobalSettingsBase, Hierarkey
from i18nfield.strings import LazyI18nString

from eventyay.base.configurations import (
    COUNTRIES_WITH_STATE,
    CSS_SETTINGS,
    DEFAULT_SETTINGS,
    NAME_SALUTION,
    NAME_SCHEMES,
    TITLE_GROUP,
)
from eventyay.base.configurations.lazy_i18n_string_list_base import (
    LazyI18nStringList,
)
from eventyay.base.reldate import RelativeDateWrapper


DEFAULTS = DEFAULT_SETTINGS.copy()
SETTINGS_AFFECTING_CSS = CSS_SETTINGS.copy()
PERSON_NAME_TITLE_GROUPS = TITLE_GROUP.copy()

PERSON_NAME_SALUTATIONS = NAME_SALUTION.copy()

PERSON_NAME_SCHEMES = NAME_SCHEMES.copy()
COUNTRIES_WITH_STATE_IN_ADDRESS = COUNTRIES_WITH_STATE.copy()

settings_hierarkey = Hierarkey(attribute_name='settings')

for k, v in DEFAULTS.items():
    settings_hierarkey.add_default(k, v['default'], v['type'])

# Eventyay Video (integrated)
settings_hierarkey.add_default('venueless_start', None, RelativeDateWrapper)
settings_hierarkey.add_default('venueless_text', None, LazyI18nString)
settings_hierarkey.add_default('review_help_text', None, LazyI18nString)
settings_hierarkey.add_default('venueless_allow_pending', 'False', bool)
settings_hierarkey.add_default('venueless_all_products', 'True', bool)
settings_hierarkey.add_default('venueless_products', '[]', list)
settings_hierarkey.add_default('venueless_questions', '[]', list)
settings_hierarkey.add_default('venueless_url', '', str)
settings_hierarkey.add_default('venueless_secret', '', str)
settings_hierarkey.add_default('venueless_issuer', '', str)
settings_hierarkey.add_default('venueless_audience', '', str)
settings_hierarkey.add_default('venueless_talk_schedule_url', '', str)
settings_hierarkey.add_default('venueless_show_public_link', False, bool)
settings_hierarkey.add_default('talk_schedule_public', None, bool)
settings_hierarkey.add_default('create_for', 'all', str)
settings_hierarkey.add_default('event_type', '', str)

# Etherpad collaborative notes integration
settings_hierarkey.add_default('etherpad_enabled', False, bool)
settings_hierarkey.add_default('etherpad_base_url', '', str)
settings_hierarkey.add_default('etherpad_api_key', '', str)
settings_hierarkey.add_default('etherpad_pad_name_pattern', '{event}-{submission}-{token}', str)

# Telemetry settings for anonymous usage data collection
# These are used by GlobalSettingsObject via settings_hierarkey
settings_hierarkey.add_default('telemetry_enabled', False, bool)
settings_hierarkey.add_default('telemetry_last_sent', None, dt.datetime)
settings_hierarkey.add_default('telemetry_endpoint', '', str)
settings_hierarkey.add_default('telemetry_api_key', '', str)
settings_hierarkey.add_default('telemetry_contact_email', '', str)

# Cloudflare Turnstile anti-abuse settings
settings_hierarkey.add_default('anti_abuse_provider', 'disabled', str)
settings_hierarkey.add_default('turnstile_site_key', '', str)
settings_hierarkey.add_default('turnstile_secret_key', '', str)
settings_hierarkey.add_default('turnstile_on_registration', False, bool)
settings_hierarkey.add_default('turnstile_login_mode', 'disabled', str)
settings_hierarkey.add_default('turnstile_failed_login_threshold', 3, int)
settings_hierarkey.add_default('turnstile_on_password_reset', False, bool)
settings_hierarkey.add_default('turnstile_on_organizer_create', False, bool)
settings_hierarkey.add_default('turnstile_on_contact', False, bool)



def i18n_uns(v):
    try:
        return LazyI18nString(json.loads(v))
    except ValueError:
        return LazyI18nString(str(v))


def _serialize_i18n(s):
    return json.dumps(s.data)


settings_hierarkey.add_type(LazyI18nString, serialize=_serialize_i18n, unserialize=i18n_uns)
settings_hierarkey.add_type(
    LazyI18nStringList,
    serialize=operator.methodcaller('serialize'),
    unserialize=LazyI18nStringList.unserialize,
)


def _serialize_rdw(rdw):
    return rdw.to_string()


def _unserialize_rdw(s):
    return RelativeDateWrapper.from_string(s)


settings_hierarkey.add_type(RelativeDateWrapper, serialize=_serialize_rdw, unserialize=_unserialize_rdw)


@settings_hierarkey.set_global(cache_namespace='global')
class GlobalSettingsObject(GlobalSettingsBase):
    slug = '_global'


EVENT_SERIES_CREATION_ENABLED = 'event_series_creation_enabled'


def is_event_series_creation_enabled(request=None) -> bool:
    _cache_attr = '_event_series_creation_enabled'
    if request is not None and hasattr(request, _cache_attr):
        return getattr(request, _cache_attr)
    gs = GlobalSettingsObject()
    result = gs.settings.get(EVENT_SERIES_CREATION_ENABLED, as_type=bool, default=True)
    if request is not None:
        setattr(request, _cache_attr, result)
    return result


MEETUP_CREATION_ENABLED = 'meetup_creation_enabled'


def is_meetup_creation_enabled(request=None) -> bool:
    _cache_attr = '_meetup_creation_enabled'
    if request is not None and hasattr(request, _cache_attr):
        return getattr(request, _cache_attr)
    gs = GlobalSettingsObject()
    result = gs.settings.get(MEETUP_CREATION_ENABLED, as_type=bool, default=False)
    if request is not None:
        setattr(request, _cache_attr, result)
    return result


class SettingsSandbox:
    """
    Transparently proxied access to event settings, handling your prefixes for you.

    :param typestr: The first part of the eventyay, e.g. ``plugin``
    :param key: The prefix, e.g. the name of your plugin
    :param obj: The event or organizer that should be queried
    """

    def __init__(self, typestr: str, key: str, obj: Model):
        self._event = obj
        self._type = typestr
        self._key = key

    def get_prefix(self):
        return f'{self._type}_{self._key}_'

    def _convert_key(self, key: str) -> str:
        return f'{self._type}_{self._key}_{key}'

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __setattr__(self, key: str, value: Any) -> None:
        if key.startswith('_'):
            return super().__setattr__(key, value)
        self.set(key, value)

    def __getattr__(self, item: str) -> Any:
        return self.get(item)

    def __getitem__(self, item: str) -> Any:
        return self.get(item)

    def __delitem__(self, key: str) -> None:
        del self._event.settings[self._convert_key(key)]

    def __delattr__(self, key: str) -> None:
        del self._event.settings[self._convert_key(key)]

    def get(self, key: str, default: Any = None, as_type: type = str):
        return self._event.settings.get(self._convert_key(key), default=default, as_type=as_type)

    def set(self, key: str, value: Any):
        self._event.settings.set(self._convert_key(key), value)


def validate_primary_font(primary_font):
    if primary_font:
        from eventyay.presale.style import SYSTEM_FONTS, get_fonts  # noqa: PLC0415
        if primary_font not in SYSTEM_FONTS and primary_font not in get_fonts():
            raise ValidationError(
                {'primary_font': _('The selected font is not allowed.')}
            )


def validate_event_settings(event, settings_dict):
    from eventyay.base.models import Event  # noqa: PLC0415
    from eventyay.base.signals import validate_event_settings  # noqa: PLC0415

    validate_primary_font(settings_dict.get('primary_font'))

    default_locale = settings_dict.get('locale')
    locales = settings_dict.get('locales', [])
    if not isinstance(locales, list):
        locales = list(locales)
    if default_locale and default_locale not in locales:
        raise ValidationError({'locale': _('Your default locale must also be enabled for your event (see box above).')})
    if settings_dict.get('attendee_names_required') and not settings_dict.get('attendee_names_asked'):
        raise ValidationError(
            {'attendee_names_required': _('You cannot require specifying attendee names if you do not ask for them.')}
        )
    if settings_dict.get('attendee_emails_required') and not settings_dict.get('attendee_emails_asked'):
        raise ValidationError(
            {'attendee_emails_required': _('You have to ask for attendee emails if you want to make them required.')}
        )
    if settings_dict.get('attendee_job_title_required') and not settings_dict.get('attendee_job_title_asked'):
        raise ValidationError(
            {
                'attendee_job_title_required': _(
                    'You have to ask for attendee job titles if you want to make them required.'
                )
            }
        )
    if settings_dict.get('order_email_required') and not settings_dict.get('order_email_asked'):
        raise ValidationError(
            {'order_email_required': _('You have to ask for order email if you want to make it required.')}
        )
    if settings_dict.get('invoice_address_required') and not settings_dict.get('invoice_address_asked'):
        raise ValidationError(
            {'invoice_address_required': _('You have to ask for invoice addresses if you want to make them required.')}
        )
    if settings_dict.get('invoice_address_company_required') and not settings_dict.get('invoice_address_required'):
        raise ValidationError(
            {
                'invoice_address_company_required': _(
                    'You have to require invoice addresses to require for company names.'
                )
            }
        )

    payment_term_last = settings_dict.get('payment_term_last')
    if payment_term_last and event.presale_end:
        if payment_term_last.date(event) < event.presale_end.date():
            raise ValidationError(
                {'payment_term_last': _('The last payment date cannot be before the end of presale.')}
            )

    if isinstance(event, Event):
        validate_event_settings.send(sender=event, settings_dict=settings_dict)


def validate_organizer_settings(organizer, settings_dict):
    validate_primary_font(settings_dict.get('primary_font'))


def global_settings_object(holder):
    if not hasattr(holder, '_global_settings_object'):
        holder._global_settings_object = GlobalSettingsObject()
    return holder._global_settings_object
