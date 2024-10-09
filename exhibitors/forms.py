from django import forms
from django.utils.translation import gettext, gettext_lazy as _

from pretix.base.forms import SettingsForm
from .models import ExhibitorInfo


class ExhibitorSettingForm(SettingsForm):
    exhibitor_url = forms.URLField(
        label=_("Exhibitor URL"),
        required=False,
    )

    exhibitor_name = forms.CharField(
        label=_("Exhibitor Name"),
        required=True,
    )

    exhibitor_description = forms.CharField(
        label=_("Exhibitor Description"),
        required=False,
    )

    exhibitor_logo = forms.ImageField(
        label=_("Exhibitor Logo"),
        required=False,
    )
    lead_scanning_enabled = forms.BooleanField(
        label=_("Lead Scanning Enabled"),
        required=False,
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        self.obj = kwargs.get('obj')
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        return data


class ExhibitorInfoForm(forms.ModelForm):
    class Meta:
        model = ExhibitorInfo
        fields = ['name', 'description', 'url', 'email', 'logo']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
