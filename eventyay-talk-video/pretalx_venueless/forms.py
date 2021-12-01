from django import forms
from django.utils.translation import gettext_lazy as _
from hierarkey.forms import HierarkeyForm


class VenuelessSettingsForm(HierarkeyForm):

    venueless_token = forms.URLField(
        help_text=_(
            "Generate a token with the trait 'world:api' in the Config -> Token Generator menu in Venueless. Leave empty to leave unchanged."
        ),
        label=_("Venueless Token"),
        required=True,
    )
