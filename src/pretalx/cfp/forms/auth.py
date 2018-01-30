from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from pretalx.common.forms.fields import PasswordConfirmationField, PasswordField
from pretalx.person.models import User


class ResetForm(forms.Form):
    login_username = forms.CharField(
        max_length=60,
        label=_('Username or email address'),
        required=True,
    )

    def clean(self):
        data = super().clean()

        try:
            if '@' in data.get('login_username'):
                user = User.objects.get(email__iexact=data.get('login_username'))
            else:
                user = User.objects.get(nick__iexact=data.get('login_username'))
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
        label=_('New password (again)'),
        required=False,
        confirm_with='password',
    )

    def clean(self):
        data = super().clean()

        if data.get('password') != data.get('password_repeat'):
            raise ValidationError(_('You entered two different passwords. Please input the same one twice!'))

        return data
