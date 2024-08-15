from django import forms
from django.utils.translation import pgettext_lazy

from pretix.base.customersso.open_id_connect import validate_config
from pretix.base.forms import I18nModelForm
from pretix.base.models.customers import CustomerSSOProvider
from pretix.base.settings import PERSON_NAME_SCHEMES


class SSOProviderForm(I18nModelForm):
    config_oidc_base_url = forms.URLField(
        label=pgettext_lazy('sso_oidc', 'Base URL'),
        required=False,
    )
    config_oidc_client_id = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Client ID'),
        required=False,
    )
    config_oidc_client_secret = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Client secret'),
        required=False,
    )
    config_oidc_scope = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Scope'),
        help_text=pgettext_lazy('sso_oidc', 'Multiple scopes separated with spaces.'),
        required=False,
    )
    config_oidc_uid_field = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'User ID field'),
        help_text=pgettext_lazy('sso_oidc', 'We will assume that the contents of the user ID fields are unique and '
                                            'can never change for a user.'),
        required=True,
        initial='sub',
    )
    config_oidc_email_field = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Email field'),
        help_text=pgettext_lazy('sso_oidc', 'We will assume that all email addresses received from the SSO provider '
                                            'are verified to really belong the the user. If this can\'t be '
                                            'guaranteed, security issues might arise.'),
        required=True,
        initial='email',
    )
    config_oidc_phone_field = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Phone field'),
        required=False,
    )

    class Meta:
        model = CustomerSSOProvider
        fields = ['is_active', 'name', 'button_label', 'method']
        widgets = {
            'method': forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        name_scheme = self.event.settings.name_scheme
        scheme = PERSON_NAME_SCHEMES.get(name_scheme)
        for fname, label, size in scheme['fields']:
            self.fields[f'config_oidc_{fname}_field'] = forms.CharField(
                label=pgettext_lazy('sso_oidc', f'{label} field').format(label=label),
                required=False,
            )

        self.fields['method'].choices = [c for c in self.fields['method'].choices if c[0]]

        for fname, f in self.fields.items():
            if fname.startswith('config_'):
                prefix, method, suffix = fname.split('_', 2)
                f.widget.attrs['data-display-dependency'] = f'input[name=method][value={method}]'

                if self.instance and self.instance.method == method:
                    f.initial = self.instance.configuration.get(suffix)

    def clean(self):
        """
        Cleans and validates the form data. If a method is specified, it collects and validates the
        configuration settings for that method, and then sets the instance's configuration.

        Returns:
            dict: The cleaned data.
        """
        data = self.cleaned_data
        if not data.get("method"):
            return data

        # Collect configuration settings for the specified method
        config = {
            fname.split('_', 2)[2]: data.get(fname)
            for fname in self.fields
            if fname.startswith(f'config_{data["method"]}_')
        }

        if data["method"] == "oidc":
            validate_config(config)

        self.instance.configuration = config
