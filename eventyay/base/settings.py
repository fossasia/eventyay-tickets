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


def i18n_uns(v):
    try:
        return LazyI18nString(json.loads(v))
    except ValueError:
        return LazyI18nString(str(v))


settings_hierarkey.add_type(LazyI18nString, serialize=lambda s: json.dumps(s.data), unserialize=i18n_uns)
settings_hierarkey.add_type(
    LazyI18nStringList,
    serialize=operator.methodcaller('serialize'),
    unserialize=LazyI18nStringList.unserialize,
)
settings_hierarkey.add_type(
    RelativeDateWrapper,
    serialize=lambda rdw: rdw.to_string(),
    unserialize=lambda s: RelativeDateWrapper.from_string(s),
)


@settings_hierarkey.set_global(cache_namespace='global')
class GlobalSettingsObject(GlobalSettingsBase):
    slug = '_global'


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
        return '%s_%s_' % (self._type, self._key)

    def _convert_key(self, key: str) -> str:
        return '%s_%s_%s' % (self._type, self._key, key)

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


def validate_event_settings(event, settings_dict):
    from pretix.base.models import Event
    from pretix.base.signals import validate_event_settings

    default_locale = settings_dict.get('locale')
    locales = settings_dict.get('locales', [])
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
    # This is not doing anything for the time being.
    # But earlier we called validate_event_settings for the organizer, too - and that didn't do anything for
    # organizer-settings either.
    #
    # N.B.: When actually fleshing out this stub, adding it to the OrganizerUpdateForm should be considered.
    pass


def global_settings_object(holder):
    if not hasattr(holder, '_global_settings_object'):
        holder._global_settings_object = GlobalSettingsObject()
    return holder._global_settings_object
