from django import forms
from django.utils.translation import gettext, gettext_lazy as _
from pretix.base.forms import SettingsForm

from .models import ExhibitorInfo


class ExhibitorInfoForm(forms.ModelForm):
    allow_voucher_access = forms.BooleanField(required=False)
    allow_lead_access = forms.BooleanField(required=False)
    lead_scanning_scope_by_device = forms.BooleanField(required=False)
    comment = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10}),
        required=False
    )
    booth_id = forms.CharField(required=False)

    class Meta:
        model = ExhibitorInfo
        fields = [
            'name',
            'description',
            'url',
            'email',
            'logo',
            'booth_id',
            'booth_name',
            'lead_scanning_enabled'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
