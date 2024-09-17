from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from pytz import common_timezones

from pretix.base.forms import SettingsForm
from pretix.base.settings import (
    PERSON_NAME_SCHEMES, PERSON_NAME_TITLE_GROUPS, validate_event_settings,
)
from pretix.control.forms import MultipleLanguagesWidget
from pretix.control.forms.event import EventWizardFoundationForm


class EventCommonSettingsForm(SettingsForm):
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_("Event timezone"),
    )

    auto_fields = [
        'locales',
        'locale',
    ]

    def clean(self):
        data = super().clean()
        settings_dict = self.event.settings.freeze()
        settings_dict.update(data)
        validate_event_settings(self.event, data)
        return data

    def __init__(self, *args, **kwargs):
        self.event = kwargs['obj']
        super().__init__(*args, **kwargs)


class EventWizardCommonFoundationForm(EventWizardFoundationForm):
    create_for = forms.MultipleChoiceField(
        choices=settings.LANGUAGES,
        label=_("Use languages"),
        widget=MultipleLanguagesWidget,
        help_text=_('Choose all languages that your event should be available in.')
    )
