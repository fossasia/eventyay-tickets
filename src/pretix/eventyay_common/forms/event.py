from django import forms
from django.utils.translation import gettext_lazy as _
from pytz import common_timezones

from pretix.base.forms import SettingsForm
from pretix.base.settings import validate_event_settings


class EventCommonSettingsForm(SettingsForm):
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_("Event timezone"),
    )

    auto_fields = [
        "locales",
        "locale",
        "region",
        "contact_mail",
        "imprint_url",
   
    ]

    def clean(self):
        data = super().clean()
        settings_dict = self.event.settings.freeze()
        settings_dict.update(data)
        validate_event_settings(self.event, data)
        return data

    def __init__(self, *args, **kwargs):
        self.event = kwargs["obj"]
        super().__init__(*args, **kwargs)
