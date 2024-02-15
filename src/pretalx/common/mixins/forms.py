import logging
from functools import partial

import dateutil.parser
from django import forms
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormField

from pretalx.common.forms.fields import ExtensionFileField
from pretalx.common.forms.utils import (
    MaxDateTimeValidator,
    MaxDateValidator,
    MinDateTimeValidator,
    MinDateValidator,
    get_help_text,
    validate_field_length,
)
from pretalx.common.phrases import phrases
from pretalx.common.templatetags.rich_text import rich_text
from pretalx.submission.models.cfp import default_fields

logger = logging.getLogger(__name__)


class ReadOnlyFlag:
    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_only = read_only
        if read_only:
            for field in self.fields.values():
                field.disabled = True

    def clean(self):
        if self.read_only:
            raise forms.ValidationError(_("You are trying to change read-only data."))
        return super().clean()


class PublicContent:
    public_fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        event = getattr(self, "event", None)
        if event and not event.feature_flags["show_schedule"]:
            return
        for field_name in self.Meta.public_fields:
            field = self.fields.get(field_name)
            if field:
                field.original_help_text = getattr(field, "original_help_text", "")
                field.added_help_text = getattr(field, "added_help_text", "") + str(
                    phrases.base.public_content
                )
                field.help_text = field.original_help_text + " " + field.added_help_text


class RequestRequire:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        count_chars = self.event.cfp.settings["count_length_in"] == "chars"
        for key in self.Meta.request_require:
            visibility = self.event.cfp.fields.get(key, default_fields()[key])[
                "visibility"
            ]
            if visibility == "do_not_ask":
                self.fields.pop(key, None)
            elif key in self.fields:
                field = self.fields[key]
                field.required = visibility == "required"
                min_value = self.event.cfp.fields.get(key, {}).get("min_length")
                max_value = self.event.cfp.fields.get(key, {}).get("max_length")
                if min_value or max_value:
                    if min_value and count_chars:
                        field.widget.attrs["minlength"] = min_value
                    if max_value and count_chars:
                        field.widget.attrs["maxlength"] = max_value
                    field.validators.append(
                        partial(
                            validate_field_length,
                            min_length=min_value,
                            max_length=max_value,
                            count_in=self.event.cfp.settings["count_length_in"],
                        )
                    )
                    field.original_help_text = getattr(field, "original_help_text", "")
                    field.added_help_text = get_help_text(
                        "",
                        min_value,
                        max_value,
                        self.event.cfp.settings["count_length_in"],
                    )
                    field.help_text = (
                        field.original_help_text + " " + field.added_help_text
                    )


class QuestionFieldsMixin:
    def get_field(self, *, question, initial, initial_object, readonly):
        from pretalx.submission.models import QuestionVariant

        read_only = readonly or question.read_only
        original_help_text = question.help_text
        help_text = rich_text(question.help_text)[len("<p>") : -len("</p>")]
        if question.is_public and self.event.feature_flags["show_schedule"]:
            help_text += " " + str(phrases.base.public_content)
        count_chars = self.event.cfp.settings["count_length_in"] == "chars"
        if question.variant == QuestionVariant.BOOLEAN:
            # For some reason, django-bootstrap4 does not set the required attribute
            # itself.
            widget = (
                forms.CheckboxInput(attrs={"required": "required", "placeholder": ""})
                if question.required
                else forms.CheckboxInput()
            )

            field = forms.BooleanField(
                disabled=read_only,
                help_text=help_text,
                label=question.question,
                required=question.required,
                widget=widget,
                initial=(
                    (initial == "True") if initial else bool(question.default_answer)
                ),
            )
            field.original_help_text = original_help_text
            return field
        if question.variant == QuestionVariant.NUMBER:
            field = forms.DecimalField(
                disabled=read_only,
                help_text=help_text,
                label=question.question,
                required=question.required,
                min_value=question.min_number,
                max_value=question.max_number,
                initial=initial,
            )
            field.original_help_text = original_help_text
            field.widget.attrs["placeholder"] = ""  # XSS
            return field
        if question.variant == QuestionVariant.STRING:
            field = forms.CharField(
                disabled=read_only,
                help_text=get_help_text(
                    help_text,
                    question.min_length,
                    question.max_length,
                    self.event.cfp.settings["count_length_in"],
                ),
                label=question.question,
                required=question.required,
                initial=initial,
                min_length=question.min_length if count_chars else None,
                max_length=question.max_length if count_chars else None,
            )
            field.original_help_text = original_help_text
            field.widget.attrs["placeholder"] = ""  # XSS
            field.validators.append(
                partial(
                    validate_field_length,
                    min_length=question.min_length,
                    max_length=question.max_length,
                    count_in=self.event.cfp.settings["count_length_in"],
                )
            )
            return field
        if question.variant == QuestionVariant.URL:
            field = forms.URLField(
                label=question.question,
                required=question.required,
                disabled=read_only,
                help_text=question.help_text,
                initial=initial,
            )
            field.original_help_text = original_help_text
            field.widget.attrs["placeholder"] = ""  # XSS
            return field
        if question.variant == QuestionVariant.TEXT:
            field = forms.CharField(
                label=question.question,
                required=question.required,
                widget=forms.Textarea,
                disabled=read_only,
                help_text=get_help_text(
                    help_text,
                    question.min_length,
                    question.max_length,
                    self.event.cfp.settings["count_length_in"],
                ),
                initial=initial,
                min_length=question.min_length if count_chars else None,
                max_length=question.max_length if count_chars else None,
            )
            field.validators.append(
                partial(
                    validate_field_length,
                    min_length=question.min_length,
                    max_length=question.max_length,
                    count_in=self.event.cfp.settings["count_length_in"],
                )
            )
            field.original_help_text = original_help_text
            field.widget.attrs["placeholder"] = ""  # XSS
            return field
        if question.variant == QuestionVariant.FILE:
            field = ExtensionFileField(
                label=question.question,
                required=question.required,
                disabled=read_only,
                help_text=help_text,
                initial=initial,
                extensions=(
                    ".png",
                    ".jpg",
                    ".gif",
                    ".jpeg",
                    ".gif",
                    ".svg",
                    ".bmp",
                    ".tif",
                    ".tiff",
                    ".pdf",
                    ".txt",
                    ".docx",
                    "doc",
                    "rtf",
                    ".pptx",
                    ".ppt",
                    ".xlsx",
                    ".xls",
                ),
            )
            field.original_help_text = original_help_text
            field.widget.attrs["placeholder"] = ""  # XSS
            return field
        if question.variant == QuestionVariant.CHOICES:
            choices = question.options.all()
            field = forms.ModelChoiceField(
                queryset=choices,
                label=question.question,
                required=question.required,
                empty_label=None,
                initial=(
                    initial_object.options.first()
                    if initial_object
                    else question.default_answer
                ),
                disabled=read_only,
                help_text=help_text,
                widget=forms.RadioSelect if len(choices) < 4 else None,
            )
            field.original_help_text = original_help_text
            field.widget.attrs["placeholder"] = ""  # XSS
            return field
        if question.variant == QuestionVariant.MULTIPLE:
            field = forms.ModelMultipleChoiceField(
                queryset=question.options.all(),
                label=question.question,
                required=question.required,
                widget=forms.CheckboxSelectMultiple,
                initial=(
                    initial_object.options.all()
                    if initial_object
                    else question.default_answer
                ),
                disabled=read_only,
                help_text=help_text,
            )
            field.original_help_text = original_help_text
            field.widget.attrs["placeholder"] = ""  # XSS
            return field
        if question.variant == QuestionVariant.DATE:
            attrs = {"class": "datepickerfield"}
            if question.min_date:
                attrs["data-date-start-date"] = question.min_date.isoformat()
            if question.max_date:
                attrs["data-date-end-date"] = question.max_date.isoformat()
            field = forms.DateField(
                label=question.question,
                required=question.required,
                disabled=read_only,
                help_text=help_text,
                initial=dateutil.parser.parse(initial).date() if initial else None,
                widget=forms.DateInput(attrs=attrs),
            )
            field.original_help_text = original_help_text
            field.widget.attrs["placeholder"] = ""  # XSS
            if question.min_date:
                field.validators.append(MinDateValidator(question.min_date))
            if question.max_date:
                field.validators.append(MaxDateValidator(question.max_date))
            return field
        elif question.variant == QuestionVariant.DATETIME:
            attrs = {"class": "datetimepickerfield"}
            if question.min_datetime:
                attrs["data-date-start-date"] = question.min_datetime.isoformat()
            if question.max_datetime:
                attrs["data-date-end-date"] = question.max_datetime.isoformat()
            field = forms.DateTimeField(
                label=question.question,
                required=question.required,
                disabled=read_only,
                help_text=help_text,
                initial=(
                    dateutil.parser.parse(initial).astimezone(self.event.tz)
                    if initial
                    else None
                ),
                widget=forms.DateTimeInput(attrs=attrs),
            )
            field.original_help_text = original_help_text
            field.widget.attrs["placeholder"] = ""  # XSS
            if question.min_datetime:
                field.validators.append(MinDateTimeValidator(question.min_datetime))
            if question.max_datetime:
                field.validators.append(MaxDateTimeValidator(question.max_datetime))
            return field
        return None

    def save_questions(self, k, v):
        """Receives a key and value from cleaned_data."""
        from pretalx.submission.models import Answer, QuestionTarget

        field = self.fields[k]
        if field.answer:
            # We already have a cached answer object, so we don't
            # have to create a new one
            if v == "" or v is None or v is False:
                field.answer.delete()
            else:
                self._save_to_answer(field, field.answer, v)
                field.answer.save()
        elif v != "" and v is not None and v is not False:
            answer = Answer(
                review=(
                    self.review
                    if field.question.target == QuestionTarget.REVIEWER
                    else None
                ),
                submission=(
                    self.submission
                    if field.question.target == QuestionTarget.SUBMISSION
                    else None
                ),
                person=(
                    self.speaker
                    if field.question.target == QuestionTarget.SPEAKER
                    else None
                ),
                question=field.question,
            )
            self._save_to_answer(field, answer, v)
            answer.save()

    def _save_to_answer(self, field, answer, value):
        if isinstance(field, forms.ModelMultipleChoiceField):
            answstr = ", ".join([str(o) for o in value])
            if not answer.pk:
                answer.save()
            else:
                answer.options.clear()
            answer.answer = answstr
            if value:
                answer.options.add(*value)
        elif isinstance(field, forms.ModelChoiceField):
            if not answer.pk:
                answer.save()
            else:
                answer.options.clear()
            if value:
                answer.options.add(value)
                answer.answer = value.answer
            else:
                answer.answer = ""
        elif isinstance(field, forms.FileField):
            if isinstance(value, UploadedFile):
                answer.answer_file.save(value.name, value)
                answer.answer = "file://" + value.name
            value = answer.answer
        else:
            answer.answer = value


class I18nHelpText:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, I18nFormField) and not field.widget.attrs.get(
                "placeholder"
            ):
                field.widget.attrs["placeholder"] = field.label


class JsonSubfieldMixin:
    def __init__(self, *args, **kwargs):
        obj = kwargs.pop("obj", None)
        super().__init__(*args, **kwargs)
        if not getattr(self, "instance", None):
            if obj:
                self.instance = obj
            elif getattr(self, "obj", None):
                self.instance = self.obj
        for field, path in self.Meta.json_fields.items():
            data_dict = getattr(self.instance, path) or {}
            if field in data_dict:
                self.fields[field].initial = data_dict.get(field)
            else:
                defaults = self.instance._meta.get_field(path).default()
                self.fields[field].initial = defaults.get(field)

    def save(self, *args, **kwargs):
        if hasattr(super(), "save"):
            instance = super().save(*args, **kwargs)
        else:
            instance = self.instance
        for field, path in self.Meta.json_fields.items():
            # We don't need nested data for now
            data_dict = getattr(instance, path) or {}
            data_dict[field] = self.cleaned_data.get(field)
            setattr(instance, path, data_dict)
        if kwargs.get("commit", True):
            instance.save()
        return instance


class HierarkeyMixin:
    """This basically vendors hierarkey.forms.HierarkeyForm, but with more
    selective saving of fields."""

    BOOL_CHOICES = HierarkeyForm.BOOL_CHOICES

    def __init__(self, *args, obj, attribute_name="settings", **kwargs):
        self.obj = obj
        self.attribute_name = attribute_name
        self._s = getattr(obj, attribute_name)
        base_initial = self._s.freeze()
        base_initial.update(**kwargs["initial"])
        kwargs["initial"] = base_initial
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        """Saves all changed values to the database."""
        super().save(*args, **kwargs)
        for name in self.Meta.hierarkey_fields:
            field = self.fields.get(name)
            value = self.cleaned_data[name]
            if isinstance(value, UploadedFile):
                # Delete old file
                fname = self._s.get(name, as_type=File)
                if fname:
                    try:
                        default_storage.delete(fname.name)
                    except OSError:  # pragma: no cover
                        logger.error("Deleting file %s failed." % fname.name)

                # Create new file
                newname = default_storage.save(self.get_new_filename(value.name), value)
                value._name = newname
                self._s.set(name, value)
            elif isinstance(value, File):
                # file is unchanged
                continue
            elif not value and isinstance(field, forms.FileField):
                # file is deleted
                fname = self._s.get(name, as_type=File)
                if fname:
                    try:
                        default_storage.delete(fname.name)
                    except OSError:  # pragma: no cover
                        logger.error("Deleting file %s failed." % fname.name)
                del self._s[name]
            elif value is None:
                del self._s[name]
            elif self._s.get(name, as_type=type(value)) != value:
                self._s.set(name, value)

    def get_new_filename(self, name: str) -> str:
        nonce = get_random_string(length=8)
        return "{}-{}/{}/{}.{}.{}".format(
            self.obj._meta.model_name,
            self.attribute_name,
            self.obj.pk,
            name,
            nonce,
            name.split(".")[-1],
        )
