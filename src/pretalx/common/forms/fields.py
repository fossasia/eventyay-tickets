from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.files.uploadedfile import UploadedFile
from django.forms import CharField, FileField, RegexField, ValidationError
from django.utils.translation import gettext_lazy as _

from pretalx.common.forms.widgets import (
    ClearableBasenameFileInput,
    ImageInput,
    PasswordConfirmationInput,
    PasswordStrengthInput,
)
from pretalx.common.templatetags.filesize import filesize

IMAGE_EXTENSIONS = (".png", ".jpg", ".gif", ".jpeg", ".svg")


class GlobalValidator:
    def __call__(self, value):
        return validate_password(value)


class NewPasswordField(CharField):
    default_validators = [GlobalValidator()]

    def __init__(self, *args, **kwargs):
        kwargs["widget"] = kwargs.get(
            "widget", PasswordStrengthInput(render_value=False)
        )
        super().__init__(*args, **kwargs)


class NewPasswordConfirmationField(CharField):
    def __init__(self, *args, **kwargs):
        kwargs["widget"] = kwargs.get(
            "widget",
            PasswordConfirmationInput(confirm_with=kwargs.pop("confirm_with", None)),
        )
        super().__init__(*args, **kwargs)


class SizeFileInput:
    """Takes the intended maximum upload size in bytes."""

    def __init__(self, *args, **kwargs):
        if "max_size" not in kwargs:  # Allow None, but only explicitly
            self.max_size = settings.FILE_UPLOAD_DEFAULT_LIMIT
        else:
            self.max_size = kwargs.pop("max_size")
        super().__init__(*args, **kwargs)
        self.size_warning = _("Please do not upload files larger than {size}!").format(
            size=filesize(self.max_size)
        )
        self.original_help_text = (
            getattr(self, "original_help_text", "") or self.help_text
        )
        self.added_help_text = getattr(self, "added_help_text", "") + self.size_warning
        self.help_text = self.original_help_text + " " + self.added_help_text
        self.widget.attrs["data-maxsize"] = self.max_size
        self.widget.attrs["data-sizewarning"] = self.size_warning

    def validate(self, value):
        super().validate(value)
        if (
            self.max_size
            and isinstance(value, UploadedFile)
            and value.size > self.max_size
        ):
            raise ValidationError(self.size_warning)


class ExtensionFileInput:
    widget = ClearableBasenameFileInput
    extensions = []

    def __init__(self, *args, **kwargs):
        extensions = kwargs.pop("extensions", None) or self.extensions or []
        self.extensions = sorted([ext.lower() for ext in extensions])
        super().__init__(*args, **kwargs)
        self.original_help_text = (
            getattr(self, "original_help_text", "") or self.help_text
        )
        self.added_help_text = (
            (getattr(self, "added_help_text", "") + " ").strip()
            + " "
            + _(
                _("Allowed filetypes: {extensions}").format(
                    extensions=", ".join(self.extensions)
                )
            )
        )
        self.help_text = self.original_help_text + " " + self.added_help_text

    def validate(self, value):
        super().validate(value)
        if value:
            filename = value.name
            extension = Path(filename).suffix.lower()
            if extension not in self.extensions:
                raise ValidationError(
                    _(
                        "This filetype ({extension}) is not allowed, it has to be one of the following: "
                    ).format(extension=extension)
                    + ", ".join(self.extensions)
                )


class SizeFileField(SizeFileInput, FileField):
    pass


class ExtensionFileField(ExtensionFileInput, SizeFileInput, FileField):
    pass


class ImageField(ExtensionFileInput, SizeFileInput, FileField):
    widget = ImageInput
    extensions = IMAGE_EXTENSIONS


class ColorField(RegexField):
    color_regex = "^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$"
    max_length = 7

    def __init__(self, *args, **kwargs):
        kwargs["regex"] = kwargs.get("regex", self.color_regex)
        super().__init__(*args, **kwargs)
        widget_class = self.widget.attrs.get("class", "")
        self.widget.attrs["class"] = f"{widget_class} colorpicker".strip()
        self.widget.attrs["pattern"] = self.color_regex[1:-1]
