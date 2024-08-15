from django import forms
from django.utils.translation import gettext_lazy as _

from pretix.base.forms import I18nModelForm
from pretix.base.models.customers import CustomerSSOClient


class SSOClientForm(I18nModelForm):
    regenerate_client_secret = forms.BooleanField(
        label=_('Invalidate old client secret and generate a new one'),
        required=False,
    )

    class Meta:
        model = CustomerSSOClient
        fields = ['is_active', 'name', 'client_id', 'client_type', 'authorization_grant_type', 'redirect_uris',
                  'allowed_scopes']
        widgets = {
            'authorization_grant_type': forms.RadioSelect,
            'client_type': forms.RadioSelect,
            'allowed_scopes': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['allowed_scopes'] = forms.MultipleChoiceField(
            label=self.fields['allowed_scopes'].label,
            help_text=self.fields['allowed_scopes'].help_text,
            required=self.fields['allowed_scopes'].required,
            initial=self.fields['allowed_scopes'].initial,
            choices=CustomerSSOClient.SCOPE_CHOICES,
            widget=forms.CheckboxSelectMultiple
        )
        if self.instance and self.instance.pk:
            self.fields['client_id'].disabled = True
        else:
            del self.fields['client_id']
            del self.fields['regenerate_client_secret']
