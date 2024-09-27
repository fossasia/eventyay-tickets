from django import forms
from django.utils.translation import gettext_lazy as _
from pytz import common_timezones

from pretix.base.forms import SettingsForm
from pretix.base.settings import PERSON_NAME_SCHEMES, PERSON_NAME_TITLE_GROUPS
from pretix.control.forms import ExtFileField


class OrganizerSettingsForm(SettingsForm):
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_("Default timezone"),
    )
    name_scheme = forms.ChoiceField(
        label=_("Name format"),
        help_text=_("Changing this after you already received "
                    "orders might lead to unexpected behavior when sorting or changing names."),
        required=True,
    )
    name_scheme_titles = forms.ChoiceField(
        label=_("Allowed titles"),
        help_text=_("If the naming scheme you defined above allows users to input a title, you can use this to "
                    "restrict the set of selectable titles."),
        required=False,
    )
    auto_fields = [
        'customer_accounts',
        'customer_accounts_native',
        'contact_mail',
        'imprint_url',
        'organizer_info_text',
        'event_list_type',
        'event_list_availability',
        'organizer_homepage_text',
        'organizer_link_back',
        'organizer_logo_image_large',
        'giftcard_length',
        'giftcard_expiry_years',
        'locales',
        'region',
        'event_team_provisioning',
        'primary_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'theme_round_borders',
        'primary_font',
        'privacy_policy'
    ]

    organizer_logo_image = ExtFileField(
        label=_('Header image'),
        ext_whitelist=(".png", ".jpg", ".gif", ".jpeg"),
        max_size=10 * 1024 * 1024,
        required=False,
        help_text=_('If you provide a logo image, we will by default not show your organization name '
                    'in the page header. By default, we show your logo with a size of up to 1140x120 pixels. You '
                    'can increase the size with the setting below. We recommend not using small details on the picture '
                    'as it will be resized on smaller screens.')
    )
    favicon = ExtFileField(
        label=_('Favicon'),
        ext_whitelist=(".ico", ".png", ".jpg", ".gif", ".jpeg"),
        required=False,
        max_size=1 * 1024 * 1024,
        help_text=_('If you provide a favicon, we will show it instead of the default pretix icon. '
                    'We recommend a size of at least 200x200px to accommodate most devices.')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name_scheme'].choices = (
            (k, _('Ask for {fields}, display like {example}').format(
                fields=' + '.join(str(vv[1]) for vv in v['fields']),
                example=v['concatenation'](v['sample'])
            ))
            for k, v in PERSON_NAME_SCHEMES.items()
        )
        self.fields['name_scheme_titles'].choices = [('', _('Free text input'))] + [
            (k, '{scheme}: {samples}'.format(
                scheme=v[0],
                samples=', '.join(v[1])
            ))
            for k, v in PERSON_NAME_TITLE_GROUPS.items()
        ]
