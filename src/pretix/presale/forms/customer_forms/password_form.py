from django import forms
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import (
    password_validators_help_texts, validate_password,
)
from django.utils.translation import gettext_lazy as _

from pretix.base.models.customers import Customer


class SetPasswordForm(forms.Form):
    required_css_class = 'required'
    error_messages = {
        'pw_mismatch': _("Please enter the same password twice"),
    }
    email = forms.EmailField(
        label=_('E-mail'),
        disabled=True
    )
    password = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={'minlength': '8', 'autocomplete': 'new-password'}),
        required=True
    )
    password_repeat = forms.CharField(
        label=_('Repeat password'),
        widget=forms.PasswordInput(attrs={'minlength': '8', 'autocomplete': 'new-password'}),
    )

    def __init__(self, customer=None, *args, **kwargs):
        self.customer = customer
        kwargs.setdefault('initial', {})
        kwargs['initial']['email'] = self.customer.email
        super().__init__(*args, **kwargs)

    def clean(self):
        password1 = self.cleaned_data.get('password', '')
        password2 = self.cleaned_data.get('password_repeat')

        if password1 and password1 != password2:
            raise forms.ValidationError({
                'password_repeat': self.error_messages['pw_mismatch'],
            }, code='pw_mismatch')

        return self.cleaned_data

    def clean_password(self):
        password1 = self.cleaned_data.get('password', '')
        if validate_password(password1, user=self.customer) is not None:
            raise forms.ValidationError(_(password_validators_help_texts()), code='pw_invalid')
        return password1


class ResetPasswordForm(forms.Form):
    required_css_class = 'required'
    error_messages = {
        'rate_limit': _("For security reasons, please wait 10 minutes before you try again."),
        'unknown': _("A user with this email address is not known in our system."),
    }
    email = forms.EmailField(
        label=_('E-mail'),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    def clean_email(self):
        if 'email' not in self.cleaned_data:
            return
        try:
            self.customer = self.request.organizer.customers.get(email=self.cleaned_data['email'].lower()
                                                                 , provider__isnull=True)
            return self.customer.email
        except Customer.DoesNotExist:
            raise forms.ValidationError(self.error_messages['unknown'], code='unknown')

    def clean(self):
        d = super().clean()
        if d.get('email') and settings.HAS_REDIS:
            from django_redis import get_redis_connection

            rc = get_redis_connection("redis")
            cnt = rc.incr('pretix_pwreset_customer_%s' % self.customer.pk)
            rc.expire('pretix_pwreset_customer_%s' % self.customer.pk, 600)
            if cnt > 2:
                raise forms.ValidationError(
                    self.error_messages['rate_limit'],
                    code='rate_limit',
                )
        return d


class ChangePasswordForm(forms.Form):
    required_css_class = 'required'
    error_messages = {
        'pw_current_wrong': _("The current password you entered was not correct."),
        'pw_mismatch': _("Please enter the same password twice"),
        'rate_limit': _("For security reasons, please wait 5 minutes before you try again."),
    }
    email = forms.EmailField(
        label=_('E-mail'),
        disabled=True
    )
    password_current = forms.CharField(
        label=_('Your current password'),
        widget=forms.PasswordInput,
        required=True
    )
    password = forms.CharField(
        label=_('New password'),
        widget=forms.PasswordInput,
        required=True
    )
    password_repeat = forms.CharField(
        label=_('Repeat password'),
        widget=forms.PasswordInput(attrs={'minlength': '8', 'autocomplete': 'new-password'}),
    )

    def __init__(self, customer, *args, **kwargs):
        self.customer = customer
        kwargs.setdefault('initial', {})
        kwargs['initial']['email'] = self.customer.email
        super().__init__(*args, **kwargs)

    def clean(self):
        password1 = self.cleaned_data.get('password', '')
        password2 = self.cleaned_data.get('password_repeat')

        if password1 and password1 != password2:
            raise forms.ValidationError({
                'password_repeat': self.error_messages['pw_mismatch'],
            }, code='pw_mismatch')

        return self.cleaned_data

    def clean_password(self):
        password1 = self.cleaned_data.get('password', '')
        if validate_password(password1, user=self.customer) is not None:
            raise forms.ValidationError(_(password_validators_help_texts()), code='pw_invalid')
        return password1

    def clean_password_current(self):
        old_pw = self.cleaned_data.get('password_current')

        if old_pw and settings.HAS_REDIS:
            from django_redis import get_redis_connection

            rc = get_redis_connection("redis")
            cnt = rc.incr('pretix_pwchange_customer_%s' % self.customer.pk)
            rc.expire('pretix_pwchange_customer_%s' % self.customer.pk, 300)
            if cnt > 10:
                raise forms.ValidationError(
                    self.error_messages['rate_limit'],
                    code='rate_limit',
                )

        if old_pw and not check_password(old_pw, self.customer.password):
            raise forms.ValidationError(
                self.error_messages['pw_current_wrong'],
                code='pw_current_wrong',
            )
