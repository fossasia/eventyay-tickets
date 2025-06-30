from django import forms
from django.utils.translation import gettext_lazy as _
from pytz import common_timezones

from pretix.base.forms import SettingsForm
from pretix.base.settings import validate_event_settings


class EventCommonSettingsForm(SettingsForm):
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_('Event timezone'),
    )

    auto_fields = [
        'locales',
        'locale',
        'logo_image',
        'logo_image_large',
        'event_logo_image',
        'logo_show_title',
        'og_image',
        'primary_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'theme_round_borders',
        'primary_font',
        'frontpage_text',
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
