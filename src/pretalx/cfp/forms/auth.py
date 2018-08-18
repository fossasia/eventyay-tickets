from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from pretalx.common.forms.fields import PasswordConfirmationField, PasswordField
from pretalx.common.phrases import phrases
from pretalx.person.models import User


class ResetForm(forms.Form):
    login_email = forms.EmailField(
        max_length=60,
        label=phrases.base.enter_email,
        required=True,
    )

    def clean(self):
        data = super().clean()
        try:
            user = User.objects.get(email__iexact=data.get('login_email'))
        except User.DoesNotExist:
            user = None

        data['user'] = user
        return data


class RecoverForm(forms.Form):
    password = PasswordField(
        label=_('New password'),
        required=False,
    )
    password_repeat = PasswordConfirmationField(
        label=phrases.base.password_repeat,
        required=False,
        confirm_with='password',
    )

    def clean(self):
        data = super().clean()
        if data.get('password') != data.get('password_repeat'):
            raise ValidationError(phrases.base.passwords_differ)
        return data
