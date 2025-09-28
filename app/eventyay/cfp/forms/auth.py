from django import forms
from django.core.exceptions import ValidationError

from eventyay.common.forms.fields import NewPasswordConfirmationField, NewPasswordField
from eventyay.common.forms.renderers import InlineFormLabelRenderer, InlineFormRenderer
from eventyay.common.text.phrases import phrases
from eventyay.base.models import User


class ResetForm(forms.Form):
    default_renderer = InlineFormLabelRenderer

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
    default_renderer = InlineFormRenderer

    password = NewPasswordField(label=phrases.base.new_password, required=False)
    password_repeat = NewPasswordConfirmationField(
        label=phrases.base.password_repeat,
        required=False,
        confirm_with='password',
    )

    def clean(self):
        data = super().clean()
        if data.get('password') != data.get('password_repeat'):
            self.add_error('password_repeat', ValidationError(phrases.base.passwords_differ))
        return data
