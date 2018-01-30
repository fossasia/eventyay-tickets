from django.contrib.auth.password_validation import validate_password
from django.forms import CharField

from pretalx.common.forms.widgets import (
    PasswordConfirmationInput, PasswordStrengthInput,
)


class GlobalValidator:

    def __call__(self, value):
        return validate_password(value)


class PasswordField(CharField):
    default_validators = [GlobalValidator()]

    def __init__(self, *args, **kwargs):
        if 'widget' not in kwargs:
            kwargs['widget'] = PasswordStrengthInput(render_value=False)
        super().__init__(*args, **kwargs)


class PasswordConfirmationField(CharField):

    def __init__(self, *args, **kwargs):
        if 'widget' not in kwargs:
            kwargs['widget'] = PasswordConfirmationInput(confirm_with=kwargs.pop('confirm_with', None))
        super().__init__(*args, **kwargs)
