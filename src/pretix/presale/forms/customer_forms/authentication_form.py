from django import forms
from django.utils.translation import gettext_lazy as _

from pretix.base.models import Customer


class AuthenticationForm(forms.Form):
    required_css_class = 'required'
    email = forms.EmailField(
        label=_("E-mail"),
        widget=forms.EmailInput(attrs={'autofocus': True})
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    error_messages = {
        'incomplete': _('You need to fill out all fields.'),
        'invalid_login': _(
            "We have not found an account with this email address and password."
        ),
        'inactive': _("This account is disabled."),
        'unverified': _("You have not yet activated your account and set a password. Please click the link in the "
                        "email we sent you. Click \"Reset password\" to receive a new email in case you cannot find "
                        "it again."),
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.customer_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email is not None and password:
            try:
                u = self.request.organizer.customers.get(email=email.lower(), provider__isnull=True)
            except Customer.DoesNotExist:
                Customer().set_password(password)
            else:
                if u.check_password(password):
                    self.customer_cache = u
            if self.customer_cache is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                )
            else:
                self.confirm_login_allowed(self.customer_cache)
        else:
            raise forms.ValidationError(
                self.error_messages['incomplete'],
                code='incomplete'
            )

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(
                self.error_messages['inactive'],
                code='inactive',
            )
        if not user.is_verified:
            raise forms.ValidationError(
                self.error_messages['unverified'],
                code='unverified',
            )

    def get_customer(self):
        return self.customer_cache
