from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from pretalx.person.models import User


class LoginForm(forms.Form):
    login_username = forms.CharField(max_length=60,
                                     label=_('Username or email address'),
                                     required=True)
    login_password = forms.CharField(widget=forms.PasswordInput,
                                     label=_('Password'),
                                     required=True)

    def clean(self):
        data = super().clean()

        if '@' in data.get('login_username'):
            try:
                uname = User.objects.get(email=data.get('login_username')).nick
            except User.DoesNotExist:
                uname = 'user@invalid'
        else:
            uname = data.get('login_username')

        user = authenticate(username=uname, password=data.get('login_password'))

        if user is None:
            raise ValidationError(_('No user account matches the entered credentials. '
                                    'Are you sure that you typed your password correctly?'))

        if not user.is_active:
            raise ValidationError(_('Sorry, your account is currently disabled.'))

        data['user'] = user
        return data
