from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile
from django.forms import CharField, FileField, ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image

from pretalx.common.forms.widgets import (
    ClearableBasenameFileInput,
    ImageInput,
    PasswordConfirmationInput,
    PasswordStrengthInput,
)

"""
SVG image uploads were possible in the past, but have been removed due to
security concerns.
SVG validation is nontrivial to the point of not having been convincingly
implemented so far, and always pose the risk of data leakage. Additionally,
Pillow does not support SVG images, and we use Pillow to strip metadata
and reduce file size.

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


class SizeFileInput:
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

    def validate(self, value):
        value = super().validate(value)
        if (
            self.max_size
            and isinstance(value, UploadedFile)
            and value.size > self.max_size
        ):
            raise ValidationError(
                _("Please do not upload files larger than {size}!").format(
                    size=SizeFileField._format_size(self.max_size)
                )
            )


class ExtensionFileInput:
    widget = ClearableBasenameFileInput

    def __init__(self, *args, **kwargs):
        extensions = kwargs.pop("extensions")
        self.extensions = [i.lower() for i in extensions]
        super().__init__(*args, **kwargs)

    def validate(self, value):
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
        return value


class SizeFileField(SizeFileInput, FileField):
    pass


class ExtensionFileField(ExtensionFileInput, SizeFileInput, FileField):
    pass


class ImageField(ExtensionFileInput, SizeFileInput, FileField):
    # TODO: add better image field widget
    widget = ImageInput

    def __init__(self, *args, **kwargs):
        self.max_width = (
            kwargs.pop("max_width", None) or settings.IMAGE_DEFAULT_MAX_WIDTH
        )
        self.max_height = (
            kwargs.pop("max_height", None) or settings.IMAGE_DEFAULT_MAX_HEIGHT
        )
        super().__init__(*args, extensions=IMAGE_EXTENSIONS, **kwargs)

    def to_python(self, data):
        """Check that the file-upload field data contains a valid image (GIF,
        JPG, PNG, etc. -- whatever Pillow supports).

        Vendored from django.forms.fields.ImageField to add EXIF data
        removal. Can't use super() because we need to patch in the
        .png.fp object for some unholy (and possibly buggy) reason.
        """
        f = super().to_python(data)
        if f is None:
            return None

        # We need to get a file object for Pillow. We might have a path or we might
        # have to read the data into memory.
        if hasattr(data, "temporary_file_path"):
            with open(data.temporary_file_path(), "rb") as temp_fp:
                file = BytesIO(temp_fp.read())
        else:
            if hasattr(data, "read"):
                file = BytesIO(data.read())
            else:
                file = BytesIO(data["content"])

        try:
            # load() could spot a truncated JPEG, but it loads the entire
            # image in memory, which is a DoS vector. See #3848 and #18520.
            image = Image.open(file)
            # verify() must be called immediately after the constructor.
            image.verify()

            # Annotating so subclasses can reuse it for their own validation
            f.image = image
            # Pillow doesn't detect the MIME type of all formats. In those
            # cases, content_type will be None.
            f.content_type = Image.MIME.get(image.format)
        except Exception as exc:
            # Pillow doesn't recognize it as an image.
            raise ValidationError(
                _(
                    "Upload a valid image. The file you uploaded was either not an "
                    "image or a corrupted image."
                )
            ) from exc
        if hasattr(f, "seek") and callable(f.seek):
            f.seek(0)

        stream = BytesIO()

        extension = ".jpg"
        if image.mode == "RGBA":
            extension = ".png"
        elif image.mode != "RGB":
            image = image.convert("RGB")

        stream.name = Path(data.name).stem + extension
        image.fp = file
        if hasattr(image, "png"):  # Yeah, idk what's up with this
            image.png.fp = file
        image_data = image.getdata()
        image_without_exif = Image.new(image.mode, image.size)
        image_without_exif.putdata(image_data)
        if self.max_height and self.max_width:
            image_without_exif.thumbnail((self.max_width, self.max_height))
        image_without_exif.save(
            stream, quality="web_high" if extension == ".jpg" else 95
        )
        stream.seek(0)
        return File(stream, name=data.name)
