import os

from django.contrib.auth.password_validation import validate_password
from django.forms import CharField, FileField, ValidationError
from django.utils.translation import ugettext_lazy as _

from pretalx.common.forms.widgets import (
    ClearableBasenameFileInput, PasswordConfirmationInput, PasswordStrengthInput,
)

"""
SVG image uploads were possible in the past, but have been removed due to
security concerns.
SVG validation is nontrivial to the point of not having been convincingly
implemented so far, and always pose the risk of data leakage.

As a compromise, users with the `is_administrator` flag are still allowed to
upload SVGs, since they are presumed to have root access to the system.
"""
IMAGE_EXTENSIONS = (".png", ".jpg", ".gif", ".jpeg")


class GlobalValidator:
    def __call__(self, value):
        return validate_password(value)


class PasswordField(CharField):
    default_validators = [GlobalValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['widget'] = kwargs.get(
            'widget', PasswordStrengthInput(render_value=False)
        )
        super().__init__(*args, **kwargs)


class PasswordConfirmationField(CharField):
    def __init__(self, *args, **kwargs):
        kwargs['widget'] = kwargs.get(
            'widget',
            PasswordConfirmationInput(confirm_with=kwargs.pop('confirm_with', None)),
        )
        super().__init__(*args, **kwargs)


class ExtensionFileField(FileField):
    widget = ClearableBasenameFileInput

    def __init__(self, *args, **kwargs):
        extension_whitelist = kwargs.pop("extension_whitelist")
        self.extension_whitelist = [i.lower() for i in extension_whitelist]
        super().__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)
        if data:
            filename = data.name
            extension = os.path.splitext(filename)[1]
            extension = extension.lower()
            if extension not in self.extension_whitelist:
                raise ValidationError(
                    _(
                        "This filetype is not allowed, it has to be one of the following: "
                    )
                    + ', '.join(self.extension_whitelist)
                )
        return data
