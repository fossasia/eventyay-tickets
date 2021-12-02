from django import forms
from django.utils.translation import gettext_lazy as _
from hierarkey.forms import HierarkeyForm


class VenuelessSettingsForm(HierarkeyForm):

    venueless_token = forms.CharField(
        help_text=_(
            "Generate a token with the trait 'world:api' in the Config -> Token Generator menu in Venueless. Leave empty to leave unchanged."
        ),
        label=_("Venueless Token"),
        required=True,
    )
    venueless_url = forms.URLField(
        help_text=_("URL of your Venueless event"),
        label=_("Venueless URL"),
        required=True,
    )

    def __init__(self, *args, initial_token=None, initial_url=None, **kwargs):
        super().__init__(*args, **kwargs)
        if initial_token:
            self.fields["venueless_token"].initial = initial_token
            self.initial["venueless_token"] = initial_token
        if initial_url:
            self.fields["venueless_url"].initial = initial_url
            self.initial["venueless_url"] = initial_url
