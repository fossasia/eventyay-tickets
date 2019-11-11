from decimal import Decimal
from functools import partial

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _

from pretalx.common.forms.utils import get_help_text, validate_field_length
from pretalx.common.phrases import phrases
from pretalx.common.templatetags.rich_text import rich_text


class ReadOnlyFlag:
    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_only = read_only
        if read_only:
            for field in self.fields.values():
                field.disabled = True

    def clean(self):
        if self.read_only:
            raise forms.ValidationError(_('You are trying to change read only data.'))
        return super().clean()


class PublicContent:

    public_fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.Meta.public_fields:
            field = self.fields.get(field_name)
            if field:
                field.help_text = (field.help_text or '') + ' ' + str(phrases.base.public_content)


class RequestRequire:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        count_chars = self.event.settings.cfp_count_length_in == 'chars'
        for key in self.Meta.request_require:
            request = self.event.settings.get(f'cfp_request_{key}')
            require = self.event.settings.get(f'cfp_require_{key}')
            if not request:
                self.fields.pop(key)
            else:
                field = self.fields[key]
                field.required = require
                min_value = self.event.settings.get(f'cfp_{key}_min_length')
                max_value = self.event.settings.get(f'cfp_{key}_max_length')
                if min_value or max_value:
                    if min_value and count_chars:
                        field.widget.attrs[f'minlength'] = min_value
                    if max_value and count_chars:
                        field.widget.attrs[f'maxlength'] = max_value
                    field.validators.append(
                        partial(
                            validate_field_length,
                            min_length=min_value,
                            max_length=max_value,
                            count_in=self.event.settings.cfp_count_length_in,
                        )
                    )
                    field.help_text = get_help_text(
                        self.fields[key].help_text,
                        min_value,
                        max_value,
                        self.event.settings.cfp_count_length_in,
                    )


class QuestionFieldsMixin:
    def get_field(self, *, question, initial, initial_object, readonly):
        from pretalx.submission.models import QuestionVariant
        help_text = rich_text(question.help_text)
        if question.is_public:
            help_text += ' ' + str(phrases.base.public_content)
        count_chars = self.event.settings.cfp_count_length_in == 'chars'
        if question.variant == QuestionVariant.BOOLEAN:
            # For some reason, django-bootstrap4 does not set the required attribute
            # itself.
            widget = (
                forms.CheckboxInput(attrs={'required': 'required', 'placeholder': ''})
                if question.required
                else forms.CheckboxInput()
            )

            return forms.BooleanField(
                disabled=readonly,
                help_text=help_text,
                label=question.question,
                required=question.required,
                widget=widget,
                initial=(initial == 'True')
                if initial
                else bool(question.default_answer),
            )
        if question.variant == QuestionVariant.NUMBER:
            field = forms.DecimalField(
                disabled=readonly,
                help_text=help_text,
                label=question.question,
                required=question.required,
                min_value=Decimal('0.00'),
                initial=initial,
            )
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == QuestionVariant.STRING:
            field = forms.CharField(
                disabled=readonly,
                help_text=get_help_text(
                    help_text,
                    question.min_length,
                    question.max_length,
                    self.event.settings.cfp_count_length_in,
                ),
                label=question.question,
                required=question.required,
                initial=initial,
                min_length=question.min_length if count_chars else None,
                max_length=question.max_length if count_chars else None,
            )
            field.widget.attrs['placeholder'] = ''  # XSS
            field.validators.append(
                partial(
                    validate_field_length,
                    min_length=question.min_length,
                    max_length=question.max_length,
                    count_in=self.event.settings.cfp_count_length_in,
                )
            )
            return field
        if question.variant == QuestionVariant.TEXT:
            field = forms.CharField(
                label=question.question,
                required=question.required,
                widget=forms.Textarea,
                disabled=readonly,
                help_text=get_help_text(
                    help_text,
                    question.min_length,
                    question.max_length,
                    self.event.settings.cfp_count_length_in,
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
                    count_in=self.event.settings.cfp_count_length_in,
                )
            )
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == QuestionVariant.FILE:
            field = forms.FileField(
                label=question.question,
                required=question.required,
                disabled=readonly,
                help_text=help_text,
                initial=initial,
            )
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == QuestionVariant.CHOICES:
            field = forms.ModelChoiceField(
                queryset=question.options.all(),
                label=question.question,
                required=question.required,
                initial=initial_object.options.first()
                if initial_object
                else question.default_answer,
                disabled=readonly,
                help_text=help_text,
            )
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == QuestionVariant.MULTIPLE:
            field = forms.ModelMultipleChoiceField(
                queryset=question.options.all(),
                label=question.question,
                required=question.required,
                widget=forms.CheckboxSelectMultiple,
                initial=initial_object.options.all()
                if initial_object
                else question.default_answer,
                disabled=readonly,
                help_text=help_text,
            )
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        return None

    def save_questions(self, k, v):
        """Receives a key and value from cleaned_data."""
        from pretalx.submission.models import Answer, QuestionTarget
        field = self.fields[k]
        if field.answer:
            # We already have a cached answer object, so we don't
            # have to create a new one
            if v == '' or v is None:
                field.answer.delete()
            else:
                self._save_to_answer(field, field.answer, v)
                field.answer.save()
        elif v != '' and v is not None:
            answer = Answer(
                review=self.review if field.question.target == QuestionTarget.REVIEWER else None,
                submission=self.submission if field.question.target == QuestionTarget.SUBMISSION else None,
                person=self.speaker if field.question.target == QuestionTarget.SPEAKER else None,
                question=field.question,
            )
            self._save_to_answer(field, answer, v)
            answer.save()

    def _save_to_answer(self, field, answer, value):
        action = 'pretalx.submission.answer.' + ('update' if answer.pk else 'create')
        if isinstance(field, forms.ModelMultipleChoiceField):
            answstr = ', '.join([str(o) for o in value])
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
                answer.answer = ''
        elif isinstance(field, forms.FileField):
            if isinstance(value, UploadedFile):
                answer.answer_file.save(value.name, value)
                answer.answer = 'file://' + value.name
            value = answer.answer
        else:
            answer.answer = value
        answer.log_action(
            action, person=self.request_user or self.speaker, data={'answer': value}
        )
