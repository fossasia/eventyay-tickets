from collections.abc import Sequence
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.files.uploadedfile import UploadedFile
from django.forms import CharField, FileField, RegexField, ValidationError
from django.utils.translation import gettext_lazy as _

from i18nfield.forms import I18nFormField
from i18nfield.strings import LazyI18nString

from eventyay.common.forms.widgets import (
    ClearableBasenameFileInput,
    EmailEditorWidget,
    I18nEmailEditorWidget,
    I18nRichTextWidget,
    ImageInput,
    PasswordConfirmationInput,
    PasswordStrengthInput,
    RichTextWidget,
)
from eventyay.common.sanitizers import sanitize_email_html, sanitize_rich_text
from eventyay.common.image import IMAGE_EXTENSIONS, validate_image
from eventyay.common.templatetags.filesize import filesize


class GlobalValidator:
    def __call__(self, value):
        return validate_password(value)


class NewPasswordField(CharField):
    default_validators = [GlobalValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['widget'] = kwargs.get('widget', PasswordStrengthInput(render_value=False))
        super().__init__(*args, **kwargs)


class NewPasswordConfirmationField(CharField):
    def __init__(self, *args, **kwargs):
        kwargs['widget'] = kwargs.get(
            'widget',
            PasswordConfirmationInput(confirm_with=kwargs.pop('confirm_with', None)),
        )
        super().__init__(*args, **kwargs)


class SizeFileInput:
    """Takes the intended maximum upload size in bytes."""

    def __init__(self, *args, **kwargs):
        self.max_size = kwargs.pop('max_size', settings.FILE_UPLOAD_DEFAULT_LIMIT)
        super().__init__(*args, **kwargs)
        
        self.size_warning = self.get_size_warning(self.max_size)
        self.widget.attrs['data-maxsize'] = self.max_size
        self.widget.attrs['data-sizewarning'] = self.size_warning
        
        if self.size_warning not in (self.help_text or ''):
            self.help_text = f'{self.help_text} {self.size_warning}'.strip() if self.help_text else self.size_warning

    @staticmethod
    def get_size_warning(max_size=None, fallback=True):
        if not max_size and fallback:
            max_size = settings.FILE_UPLOAD_DEFAULT_LIMIT
        return _('The upload limit is {size}.').format(size=filesize(max_size))

    def validate(self, value):
        super().validate(value)
        if self.max_size and isinstance(value, UploadedFile) and value.size > self.max_size:
            raise ValidationError(self.size_warning)


class ExtensionFileInput:
    widget = ClearableBasenameFileInput
    extensions = {}

    def __init__(self, *args, **kwargs):
        self.extensions = kwargs.pop('extensions', None) or self.extensions or {}
        super().__init__(*args, **kwargs)
        
        if self.extensions:
            content_types = set()
            for ext in self.extensions.values():
                content_types.update(ext)
            self.widget.attrs['accept'] = ','.join(content_types)
            
            supported_formats = ', '.join(sorted(self.extensions.keys()))
            extension_help_text = _('Supported formats: {formats}').format(formats=supported_formats)
            
            if extension_help_text not in (self.help_text or ''):
                self.help_text = f'{self.help_text} {extension_help_text}'.strip() if self.help_text else extension_help_text

    def validate(self, value):
        super().validate(value)
        if value:
            filename = value.name
            extension = Path(filename).suffix.lower()
            if extension not in self.extensions.keys():
                allowed_formats = ', '.join(sorted(self.extensions.keys()))
                raise ValidationError(
                    _("The file type '{extension}' is not supported. Please upload one of the supported formats: {formats}.").format(
                        extension=extension,
                        formats=allowed_formats
                    )
                )


class SizeFileField(SizeFileInput, FileField):
    pass


class ExtensionFileField(ExtensionFileInput, SizeFileInput, FileField):
    pass


class ImageField(ExtensionFileInput, SizeFileInput, FileField):
    widget = ImageInput
    extensions = IMAGE_EXTENSIONS

    def clean(self, value, initial=None):
        value = super().clean(value, initial)
        if value:
            validate_image(value)
        return value


class RichTextField(CharField):
    """A CharField that uses the Tiptap rich text editor widget.

    Sanitizes the submitted HTML server-side using ``sanitize_rich_text``
    before returning the cleaned value.  Safe tags: p, br, strong, b, em,
    i, u, ul, ol, li, a (http/https only), blockquote.
    """

    widget = RichTextWidget

    def clean(self, value: str) -> str:
        value = super().clean(value)
        return sanitize_rich_text(value) if value else value


class I18nRichTextFormField(I18nFormField):
    """I18n form field for rich text using the Tiptap richtext editor.

    Sanitizes each locale value with the provided sanitizer (defaults to ``sanitize_rich_text``)
    after validation.
    """

    widget = I18nRichTextWidget

    def __init__(self, *args, sanitizer=None, **kwargs):
        self.sanitizer = sanitizer or sanitize_rich_text
        kwargs.setdefault('widget', I18nRichTextWidget)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        result = super().clean(value)
        if isinstance(result, LazyI18nString):
            if isinstance(result.data, dict):
                return LazyI18nString(
                    {locale: self.sanitizer(text) if text else text for locale, text in result.data.items()}
                )
            elif isinstance(result.data, str):
                return LazyI18nString(self.sanitizer(result.data) if result.data else result.data)
        elif isinstance(result, str):
            return self.sanitizer(result) if result else result
        return result


class EmailBodyField(CharField):
    """A CharField for email body editing using the Tiptap email editor profile.

    The email profile extends the rich text profile with a placeholder
    variable insertion menu.  HTML is sanitized with ``sanitize_email_html``
    which uses a slightly broader tag set than ``RichTextField`` but does
    not inject ``rel`` attributes that may confuse email clients.

    Args:
        placeholders: Names of template variables available for insertion,
            e.g. ``['attendee_name', 'event_name', 'order_code']``.
        preview_url: Optional URL for the email preview AJAX endpoint.
    """

    def __init__(
        self,
        *args,
        placeholders: Sequence[str] | None = None,
        preview_url: str = '',
        **kwargs,
    ) -> None:
        if 'widget' not in kwargs:
            kwargs['widget'] = EmailEditorWidget(placeholders=placeholders, preview_url=preview_url)
        super().__init__(*args, **kwargs)

    def clean(self, value: str) -> str:
        value = super().clean(value)
        return sanitize_email_html(value) if value else value


class I18nEmailBodyFormField(I18nFormField):
    """I18n form field for Message center email bodies using the Tiptap email editor.

    Sanitizes each locale value with ``sanitize_email_html`` after validation.

    Args:
        placeholders: Names of template variables available for insertion,
            e.g. ``['attendee_name', 'event_name', 'order_code']``.
        preview_url: Optional URL for the email preview AJAX endpoint.
    """

    widget = I18nEmailEditorWidget

    def __init__(
        self,
        *args,
        placeholders: Sequence[str] | None = None,
        preview_url: str = '',
        **kwargs,
    ) -> None:
        widget_kwargs = kwargs.pop('widget_kwargs', {})
        if placeholders is not None:
            widget_kwargs.setdefault('placeholders', placeholders)
        if preview_url:
            widget_kwargs.setdefault('preview_url', preview_url)
        kwargs['widget_kwargs'] = widget_kwargs
        kwargs.setdefault('widget', I18nEmailEditorWidget)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        result = super().clean(value)
        if isinstance(result, LazyI18nString):
            if isinstance(result.data, dict):
                return LazyI18nString(
                    {locale: sanitize_email_html(text) if text else text for locale, text in result.data.items()}
                )
            elif isinstance(result.data, str):
                return LazyI18nString(sanitize_email_html(result.data) if result.data else result.data)
        elif isinstance(result, str):
            return sanitize_email_html(result) if result else result
        return result


class ColorField(RegexField):
    color_regex = '^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
    max_length = 7

    def __init__(self, *args, **kwargs):
        kwargs['regex'] = kwargs.get('regex', self.color_regex)
        super().__init__(*args, **kwargs)
        widget_class = self.widget.attrs.get('class', '')
        self.widget.attrs['class'] = f'{widget_class} colorpicker'.strip()
        self.widget.attrs['pattern'] = self.color_regex[1:-1]
