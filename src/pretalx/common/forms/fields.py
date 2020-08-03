from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.files.uploadedfile import UploadedFile
from django.forms import CharField, FileField, ValidationError
from django.utils.translation import gettext_lazy as _

from pretalx.common.forms.widgets import (
    ClearableBasenameFileInput,
    PasswordConfirmationInput,
    PasswordStrengthInput,
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
        kwargs["widget"] = kwargs.get(
            "widget", PasswordStrengthInput(render_value=False)
        )
        super().__init__(*args, **kwargs)


class PasswordConfirmationField(CharField):
    def __init__(self, *args, **kwargs):
        kwargs["widget"] = kwargs.get(
            "widget",
            PasswordConfirmationInput(confirm_with=kwargs.pop("confirm_with", None)),
        )
        super().__init__(*args, **kwargs)


class SizeFileField(FileField):
    """Takes the intended maximum upload size in bytes."""

    def __init__(self, *args, **kwargs):
        if "max_size" not in kwargs:  # Allow None, but only explicitly
            self.max_size = settings.FILE_UPLOAD_DEFAULT_LIMIT
        else:
            self.max_size = kwargs.pop("max_size")
        super().__init__(*args, **kwargs)

    @staticmethod
    def _format_size(num):
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:  # Future proof 10/10
            if abs(num) < 1024:
                return f"{num:3.1f}{unit}B"
            num /= 1024
        return f"{num:.1f}YiB"  # Future proof 11/10

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)
        if (
            self.max_size
            and isinstance(data, UploadedFile)
            and data.size > self.max_size
        ):
            raise ValidationError(
                _("Please do not upload files larger than {size}!").format(
                    size=SizeFileField._format_size(self.max_size)
                )
            )
        return data


class ExtensionFileField(SizeFileField):
    widget = ClearableBasenameFileInput

    def __init__(self, *args, **kwargs):
        extensions = kwargs.pop("extensions")
        self.extensions = [i.lower() for i in extensions]
        super().__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)
        if data:
            filename = data.name
            extension = Path(filename).suffix.lower()
            if extension not in self.extensions:
                raise ValidationError(
                    _(
                        "This filetype ({extension}) is not allowed, it has to be one of the following: "
                    ).format(extension=extension)
                    + ", ".join(self.extensions)
                )
        return data
