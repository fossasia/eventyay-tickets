import json
import logging
from datetime import timedelta
from functools import partial

import dateutil.parser
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django_countries.fields import Country, CountryField
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormField

from eventyay.common.forms.fields import ExtensionFileField
from eventyay.common.forms.validators import (
    MaxDateTimeValidator,
    MaxDateValidator,
    MinDateTimeValidator,
    MinDateValidator,
)
from eventyay.common.forms.widgets import HtmlDateInput, HtmlDateTimeInput
from eventyay.common.text.phrases import phrases
from eventyay.common.utils.language import localize_event_text
from eventyay.common.session_video import exclude_session_video_from_cfp_questions
from eventyay.common.video_embed import get_video_embed_info, parse_video_urls
from eventyay.helpers.countries import CachedCountries
from eventyay.helpers.escapejson import escapejson_attr
from eventyay.base.models import TalkQuestion, TalkQuestionTarget, TalkQuestionVariant
from eventyay.base.models.cfp import BUILTIN_FIELD_KEYS, normalize_field_order, default_fields

logger = logging.getLogger(__name__)


class EventLocalizedModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return localize_event_text(getattr(obj, 'answer', obj))


class EventLocalizedModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return localize_event_text(getattr(obj, 'answer', obj))


class ReadOnlyFlag:
    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_only = read_only
        if read_only:
            for field in self.fields.values():
                field.disabled = True

    def clean(self):
        if self.read_only:
            raise forms.ValidationError(_('You are trying to change read-only data.'))
        return super().clean()


class PublicContent:
    public_fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        event = getattr(self, 'event', None)
        if event and not event.get_feature_flag('show_schedule'):
            return
        for field_name in self.Meta.public_fields:
            if event and hasattr(event, 'cfp') and not event.cfp.is_field_public(field_name):
                continue
            field = self.fields.get(field_name)
            if field:
                field.original_help_text = getattr(field, 'original_help_text', '')
                field.added_help_text = getattr(field, 'added_help_text', '') + str(phrases.base.public_content)
                field.help_text = field.original_help_text + ' ' + field.added_help_text


class RequestRequire:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _cfp = getattr(self.event, 'cfp', None) if hasattr(self.event, 'cfp') else None
        _cfp_settings = _cfp.settings if _cfp else {}
        _cfp_fields = _cfp.fields if _cfp else default_fields()
        count_chars = _cfp_settings.get('count_length_in', 'chars') == 'chars'
        count_length_in = _cfp_settings.get('count_length_in', 'chars')
        for key in self.Meta.request_require:
            visibility = _cfp_fields.get(key, default_fields()[key])['visibility']
            if visibility == 'do_not_ask':
                self.fields.pop(key, None)
            elif field := self.fields.get(key):
                field.required = visibility == 'required'
                min_value = _cfp_fields.get(key, {}).get('min_length')
                max_value = _cfp_fields.get(key, {}).get('max_length')
                if min_value or max_value:
                    if min_value and count_chars:
                        field.widget.attrs['minlength'] = min_value
                    if max_value and count_chars:
                        field.widget.attrs['maxlength'] = max_value
                    field.validators.append(
                        partial(
                            self.validate_field_length,
                            min_length=min_value,
                            max_length=max_value,
                            count_in=count_length_in,
                        )
                    )
                    field.original_help_text = getattr(field, 'original_help_text', '')
                    field.added_help_text = self.get_help_text(
                        '',
                        min_value,
                        max_value,
                        count_length_in,
                    )
                    field.help_text = field.original_help_text + ' ' + field.added_help_text

    @staticmethod
    def get_help_text(text, min_length, max_length, count_in='chars'):
        if not min_length and not max_length:
            return text
        if text:
            text = str(text) + ' '
        else:
            text = ''
        texts = {
            'minmaxwords': _('Please write between {min_length} and {max_length} words.'),
            'minmaxchars': _('Please write between {min_length} and {max_length} characters.'),
            'minwords': _('Please write at least {min_length} words.'),
            'minchars': _('Please write at least {min_length} characters.'),
            'maxwords': _('Please write at most {max_length} words.'),
            'maxchars': _('Please write at most {max_length} characters.'),
        }
        length = ('min' if min_length else '') + ('max' if max_length else '')
        message = texts[length + count_in].format(min_length=min_length, max_length=max_length)
        return (text + str(message)).strip()

    @staticmethod
    def validate_field_length(value, min_length, max_length, count_in):
        if count_in == 'chars':
            # Line breaks should only be counted as one character
            length = len(value.replace('\r\n', '\n'))
        else:
            length = len(value.split())
        if (min_length and min_length > length) or (max_length and max_length < length):
            error_message = RequestRequire.get_help_text('', min_length, max_length, count_in)
            errors = {
                'chars': _('You wrote {count} characters.'),
                'words': _('You wrote {count} words.'),
            }
            error_message += ' ' + str(errors[count_in]).format(count=length)
            raise forms.ValidationError(error_message)


class QuestionFieldsMixin:
    @staticmethod
    def _resolve_single_choice_initial(initial_object, choices, default_answer):
        """Return a valid AnswerOption initial, ignoring removed options."""
        if initial_object:
            return initial_object.options.filter(pk__in=choices.values_list('pk', flat=True)).first()
        if default_answer:
            return choices.filter(answer=default_answer).first()
        return None

    @staticmethod
    def _resolve_multiple_choice_initial(initial_object, choices, default_answer):
        """Return initial values for checkboxes, ignoring removed options.

        Returns a list of valid AnswerOption instances for saved answers.
        For unsaved answers, ``default_answer`` is passed through unchanged, since
        it is configured by question settings and consumed directly by form fields.
        """
        if initial_object:
            return list(initial_object.options.filter(pk__in=choices.values_list('pk', flat=True)))
        if default_answer:
            return default_answer
        return []

    def get_question_queryset(self, target, event):
        qs = TalkQuestion.all_objects.filter(
            event=event,
            active=True,
            is_imported=False,
            target=target,
        )
        return exclude_session_video_from_cfp_questions(qs).order_by('position')

    def inject_questions_into_fields(
        self,
        target,
        event,
        submission=None,
        speaker=None,
        review=None,
        track=None,
        submission_type=None,
        readonly=False,
    ):
        """
        Injects custom question fields into the form, filtered by track/type and pre-filled with answers.

        Args:
            target (str): TalkQuestionTarget (SUBMISSION/SPEAKER/REVIEWER).
            event (Event): Event context.
            submission, speaker, review: Answer contexts.
            track, submission_type: Visibility filters.
            readonly (bool): If True, fields are disabled.
        """
        questions = self.get_question_queryset(target, event)
        # Apply filters based on submission context
        if track:
            questions = questions.filter(Q(tracks__in=[track]) | Q(tracks__isnull=True))
        if submission_type:
            questions = questions.filter(Q(submission_types__in=[submission_type]) | Q(submission_types__isnull=True))

        # Pre-fetch existing answers
        target_object = None
        if target == TalkQuestionTarget.SUBMISSION:
            target_object = submission
        elif target == TalkQuestionTarget.SPEAKER:
            target_object = speaker
        elif target == TalkQuestionTarget.REVIEWER:
            target_object = review

        answers_by_question = {}
        if target_object:
            # Build a lookup dict to avoid scanning all answers for each question
            for answer in target_object.answers.all():
                # Preserve the first answer per question to match previous behavior
                answers_by_question.setdefault(answer.question_id, answer)

        for question in questions.prefetch_related('options'):
            initial_object = None
            initial = question.default_answer

            if target_object:
                answer = answers_by_question.get(question.id)
                if answer:
                    initial_object = answer
                    initial = answer.answer_file if question.variant == TalkQuestionVariant.FILE else answer.answer

            field = self.get_field(
                question=question,
                initial=initial,
                initial_object=initial_object,
                readonly=readonly,
            )
            if field is None:
                continue
            field.question = question
            field.answer = initial_object

            if question.dependency_question_id:
                field.widget.attrs['data-question-dependency'] = question.dependency_question_id
                field.widget.attrs['data-question-dependency-values'] = escapejson_attr(json.dumps(question.dependency_values))
                if question.variant != TalkQuestionVariant.MULTIPLE:
                    field.widget.attrs['required'] = question.required
                    field._required = question.required
                field.required = False

            field_name = f'question_{question.pk}'
            if field_name not in self.fields:
                self.fields[field_name] = field

    def get_field(self, *, question, initial, initial_object, readonly):
        from eventyay.base.models import TalkQuestionVariant
        from eventyay.base.templatetags.rich_text import rich_text

        read_only = readonly or question.read_only
        label_text = localize_event_text(question.question)
        original_help_text = localize_event_text(question.help_text)
        help_text = rich_text(original_help_text or '')[len('<p>') : -len('</p>')]
        if question.is_public and self.event.get_feature_flag('show_schedule'):
            help_text += ' ' + str(phrases.base.public_content)
        count_chars = (
            getattr(getattr(self.event, 'cfp', None), 'settings', {}).get('count_length_in', 'chars') == 'chars'
        )
        if question.variant == TalkQuestionVariant.BOOLEAN:
            # For some reason, django-bootstrap4 does not set the required attribute
            # itself.
            widget = (
                forms.CheckboxInput(attrs={'required': 'required', 'placeholder': ''})
                if question.required
                else forms.CheckboxInput()
            )

            field = forms.BooleanField(
                disabled=read_only,
                help_text=help_text,
                label=label_text,
                required=question.required,
                widget=widget,
                initial=((initial == 'True') if initial else bool(question.default_answer)),
            )
            field.original_help_text = original_help_text
            return field
        if question.variant == TalkQuestionVariant.NUMBER:
            field = forms.DecimalField(
                disabled=read_only,
                help_text=help_text,
                label=label_text,
                required=question.required,
                min_value=question.min_number,
                max_value=question.max_number,
                initial=initial,
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == TalkQuestionVariant.STRING:
            field = forms.CharField(
                disabled=read_only,
                help_text=RequestRequire.get_help_text(
                    help_text,
                    question.min_length,
                    question.max_length,
                    getattr(getattr(self.event, 'cfp', None), 'settings', {}).get('count_length_in', 'chars'),
                ),
                label=label_text,
                required=question.required,
                initial=initial,
                min_length=question.min_length if count_chars else None,
                max_length=question.max_length if count_chars else None,
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            field.validators.append(
                partial(
                    RequestRequire.validate_field_length,
                    min_length=question.min_length,
                    max_length=question.max_length,
                    count_in=getattr(getattr(self.event, 'cfp', None), 'settings', {}).get('count_length_in', 'chars'),
                )
            )
            return field
        if question.variant == TalkQuestionVariant.URL:
            field = forms.URLField(
                label=label_text,
                required=question.required,
                disabled=read_only,
                help_text=original_help_text,
                initial=initial,
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == TalkQuestionVariant.VIDEO:
            video_help = original_help_text or _(
                'Paste YouTube or Vimeo URLs, one per line. '
                'Publish this field to embed the videos on the public session page.'
            )

            def validate_video_urls(value):
                urls = parse_video_urls(value)
                if value and str(value).strip() and not urls:
                    raise ValidationError(
                        _('Please enter valid YouTube or Vimeo URLs, one per line.')
                    )
                for url in urls:
                    if get_video_embed_info(url) is None:
                        raise ValidationError(
                            _('Please enter valid YouTube or Vimeo URLs, one per line.')
                        )

            field = forms.CharField(
                label=label_text,
                required=question.required,
                disabled=read_only,
                help_text=video_help,
                initial=initial,
                widget=forms.Textarea(attrs={'rows': 3}),
                validators=[validate_video_urls],
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = (
                'https://www.youtube.com/watch?v=…\nhttps://vimeo.com/…'
            )
            return field
        if question.variant == TalkQuestionVariant.TEXT:
            field = forms.CharField(
                label=label_text,
                required=question.required,
                widget=forms.Textarea,
                disabled=read_only,
                help_text=RequestRequire.get_help_text(
                    help_text,
                    question.min_length,
                    question.max_length,
                    getattr(getattr(self.event, 'cfp', None), 'settings', {}).get('count_length_in', 'chars'),
                ),
                initial=initial,
                min_length=question.min_length if count_chars else None,
                max_length=question.max_length if count_chars else None,
            )
            field.validators.append(
                partial(
                    RequestRequire.validate_field_length,
                    min_length=question.min_length,
                    max_length=question.max_length,
                    count_in=getattr(getattr(self.event, 'cfp', None), 'settings', {}).get('count_length_in', 'chars'),
                )
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == TalkQuestionVariant.FILE:
            field = ExtensionFileField(
                label=label_text,
                required=question.required,
                disabled=read_only,
                help_text=help_text,
                initial=initial,
                extensions={
                    '.png': ['image/png', '.png'],
                    '.jpg': ['image/jpeg', '.jpg'],
                    '.gif': ['image/gif', '.gif'],
                    '.jpeg': ['image/jpeg', '.jpeg'],
                    '.svg': ['image/svg+xml', '.svg'],
                    '.bmp': ['image/bmp', '.bmp'],
                    '.tif': ['image/tiff', '.tif'],
                    '.tiff': ['image/tiff', '.tiff'],
                    '.pdf': [
                        'application/pdf',
                        'application/x-pdf',
                        'application/acrobat',
                        'applications/vnd.pdf',
                        '.pdf',
                    ],
                    '.txt': ['text/plain'],
                    '.docx': [
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/msword',
                        '.docx',
                    ],
                    'doc': ['.doc'],
                    'rtf': ['application/rtf'],
                    '.pptx': [
                        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                        'application/vnd.ms-powerpoint',
                        '.pptx',
                    ],
                    '.ppt': ['.ppt'],
                    '.xlsx': [
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        'application/vnd.ms-excel',
                        '.xlsx',
                    ],
                    '.xls': ['.xls'],
                },
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == TalkQuestionVariant.CHOICES:
            choices = question.options.all()
            initial_value = self._resolve_single_choice_initial(
                initial_object, choices, question.default_answer
            )
            field = EventLocalizedModelChoiceField(
                queryset=choices,
                label=label_text,
                required=question.required,
                empty_label=None if question.required else _('— No selection —'),
                # Django 6 clears empty_label for RadioSelect unless blank=True.
                blank=not question.required,
                initial=initial_value,
                disabled=read_only,
                help_text=help_text,
                widget=forms.RadioSelect,
            )
            field.original_help_text = original_help_text
            return field
        if question.variant == TalkQuestionVariant.SELECT:
            choices = question.options.all()
            initial_value = self._resolve_single_choice_initial(
                initial_object, choices, question.default_answer
            )
            field = EventLocalizedModelChoiceField(
                queryset=choices,
                label=label_text,
                required=question.required,
                empty_label=(
                    None
                    if question.required and initial_value is not None
                    else _('— No selection —')
                ),
                initial=initial_value,
                disabled=read_only,
                help_text=help_text,
                widget=forms.Select(attrs={'class': 'enhanced'}),
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == TalkQuestionVariant.MULTIPLE:
            choices = question.options.all()
            field = EventLocalizedModelMultipleChoiceField(
                queryset=choices,
                label=label_text,
                required=question.required,
                widget=(
                    forms.CheckboxSelectMultiple
                    if len(choices) < 8
                    else forms.SelectMultiple(attrs={'class': 'enhanced'})
                ),
                initial=self._resolve_multiple_choice_initial(
                    initial_object, choices, question.default_answer
                ),
                disabled=read_only,
                help_text=help_text,
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        if question.variant == TalkQuestionVariant.DATE:
            attrs = {}
            if question.min_date:
                attrs['data-date-start-date'] = question.min_date.isoformat()
            if question.max_date:
                attrs['data-date-end-date'] = question.max_date.isoformat()
            field = forms.DateField(
                label=label_text,
                required=question.required,
                disabled=read_only,
                help_text=help_text,
                initial=dateutil.parser.parse(initial).date() if initial else None,
                widget=HtmlDateInput(attrs=attrs),
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            if question.min_date:
                field.validators.append(MinDateValidator(question.min_date))
            if question.max_date:
                field.validators.append(MaxDateValidator(question.max_date))
            return field
        elif question.variant == TalkQuestionVariant.DATETIME:
            attrs = {}
            if question.min_datetime:
                attrs['min'] = question.min_datetime.isoformat()
            if question.max_datetime:
                attrs['max'] = question.max_datetime.isoformat()
            field = forms.DateTimeField(
                label=label_text,
                required=question.required,
                disabled=read_only,
                help_text=help_text,
                initial=(dateutil.parser.parse(initial).astimezone(self.event.tz) if initial else None),
                widget=HtmlDateTimeInput(attrs=attrs),
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            if question.min_datetime:
                field.validators.append(MinDateTimeValidator(question.min_datetime))
            if question.max_datetime:
                field.validators.append(MaxDateTimeValidator(question.max_datetime))
            return field
        if question.variant == TalkQuestionVariant.COUNTRY:
            field = CountryField(countries=CachedCountries).formfield(
                label=label_text,
                required=question.required,
                disabled=read_only,
                help_text=help_text,
                initial=initial or None,
            )
            field.original_help_text = original_help_text
            field.widget.attrs['placeholder'] = ''  # XSS
            return field
        return None

    def save_questions(self, key, value):
        """Receives a key and value from cleaned_data."""
        from eventyay.base.models import Answer, TalkQuestionTarget

        field = self.fields[key]
        if field.answer:
            # We already have a cached answer object, so we don't
            # have to create a new one
            if value == '' or value is None or value is False:
                field.answer.delete()
            else:
                self._save_to_answer(field, field.answer, value)
        elif value != '' and value is not None and value is not False:
            answer = Answer(
                review=(self.review if field.question.target == TalkQuestionTarget.REVIEWER else None),
                submission=(self.submission if field.question.target == TalkQuestionTarget.SUBMISSION else None),
                person=(self.speaker if field.question.target == TalkQuestionTarget.SPEAKER else None),
                question=field.question,
            )
            self._save_to_answer(field, answer, value)

    def _save_to_answer(self, field, answer, value):
        if isinstance(field, forms.ModelMultipleChoiceField):
            answstr = ', '.join([str(option) for option in value])
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
                answer.answer_file.save(value.name, value, save=False)
                answer.answer = 'file://' + value.name
            value = answer.answer
        elif value is not None and isinstance(value, Country):
            answer.answer = value.code
        else:
            answer.answer = value
        answer.save()

    def clean(self):
        cleaned_data = super().clean()

        question_cache = {
            field.question.pk: field.question
            for field_name, field in self.fields.items()
            if field_name.startswith('question_') and hasattr(field, 'question')
        }

        def question_is_visible(parent_id, dep_values):
            if parent_id not in question_cache:
                return False
            parent_question = question_cache[parent_id]
            if parent_question.dependency_question_id and not question_is_visible(
                parent_question.dependency_question_id, parent_question.dependency_values
            ):
                return False
            parent_field_name = f'question_{parent_id}'
            if parent_field_name not in cleaned_data:
                return False
            parent_value = cleaned_data[parent_field_name]
            if parent_value is None or parent_value == '':
                return False
            if isinstance(parent_value, bool):
                return ('True' in dep_values and parent_value) or ('False' in dep_values and not parent_value)
            if isinstance(parent_value, str):
                return parent_value in dep_values
            if hasattr(parent_value, '__iter__'):
                return any(
                    (str(v.pk) if hasattr(v, 'pk') else str(v)) in dep_values
                    for v in parent_value
                )
            if hasattr(parent_value, 'pk'):
                return str(parent_value.pk) in dep_values
            return str(parent_value) in dep_values

        for field_name, field in self.fields.items():
            if not field_name.startswith('question_') or not hasattr(field, 'question'):
                continue
            question = field.question
            if not question.dependency_question_id or not question.required:
                continue
            if not question_is_visible(question.dependency_question_id, question.dependency_values):
                continue
            value = cleaned_data.get(field_name)
            if value is None or value == '' or (hasattr(value, '__len__') and len(value) == 0):
                self.add_error(field_name, forms.ValidationError(_('This field is required.')))

        return cleaned_data


class I18nHelpText:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, I18nFormField) and not field.widget.attrs.get('placeholder'):
                field.widget.attrs['placeholder'] = field.label


class JsonSubfieldMixin:
    def __init__(self, *args, **kwargs):
        obj = kwargs.pop('obj', None)
        super().__init__(*args, **kwargs)
        if not getattr(self, 'instance', None):
            if obj:
                self.instance = obj
            elif getattr(self, 'obj', None):
                self.instance = self.obj
        for field, path in self.Meta.json_fields.items():
            data_dict = getattr(self.instance, path) or {}
            if field in data_dict:
                self.fields[field].initial = data_dict.get(field)
            else:
                defaults = self.instance._meta.get_field(path).default()
                self.fields[field].initial = defaults.get(field)

    def save(self, *args, **kwargs):
        if getattr(super(), 'save', None):
            instance = super().save(*args, **kwargs)
        else:
            instance = self.instance
        modified_paths = set()
        for field, path in self.Meta.json_fields.items():
            # Fields may be conditionally removed (e.g. feature-gated); leave any
            # stored value untouched rather than overwriting it with None.
            if field not in self.fields:
                continue
            # We don't need nested data for now
            data_dict = getattr(instance, path) or {}
            data_dict[field] = self.cleaned_data.get(field)
            setattr(instance, path, data_dict)
            modified_paths.add(path)
        if kwargs.get('commit', True):
            # Only save the modified JSON fields to avoid overwriting other model fields
            instance.save(update_fields=list(modified_paths))
        return instance


class HierarkeyMixin:
    """This basically vendors hierarkey.forms.HierarkeyForm, but with more
    selective saving of fields."""

    BOOL_CHOICES = HierarkeyForm.BOOL_CHOICES

    def __init__(self, *args, obj, attribute_name='settings', **kwargs):
        self.obj = obj
        self.attribute_name = attribute_name
        self._s = getattr(obj, attribute_name)
        base_initial = self._s.freeze()
        base_initial.update(**kwargs['initial'])
        kwargs['initial'] = base_initial
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
                        logger.error('Deleting file %s failed.', fname.name)

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
                        logger.error('Deleting file %s failed.', fname.name)
                del self._s[name]
            elif value is None:
                del self._s[name]
            elif self._s.get(name, as_type=type(value)) != value:
                self._s.set(name, value)

    def get_new_filename(self, name: str) -> str:
        nonce = get_random_string(length=8)
        suffix = name.split('.')[-1]
        return f'{self.obj._meta.model_name}-{self.attribute_name}/{self.obj.pk}/{name}.{nonce}.{suffix}'


class ConfiguredFieldOrderMixin:
    def order_fields_by_config(self, config_key):
        _cfp = getattr(self.event, 'cfp', None) if hasattr(self.event, 'cfp') else None
        fields_config = (_cfp.settings.get('fields_config', {}).get(config_key, []) if _cfp else [])
        if fields_config:
            builtin_names = set(BUILTIN_FIELD_KEYS.get(config_key, ()))
            # Ensure every built-in field is present at its canonical position.
            # This handles both config-with-no-builtins and partially-populated
            # configs (e.g. a new built-in added after the config was saved).
            fields_config = normalize_field_order(fields_config, config_key)
            configured_names = []
            for item in fields_config:
                name = None
                if isinstance(item, str):
                    name = item
                elif isinstance(item, dict):
                    # Try common keys for field name in configuration dicts
                    name = item.get('name') or item.get('field')
                else:
                    logger.warning('Field configuration item %r is ignored (unknown type)', item)

                if not name:
                    continue

                # Config stores custom question IDs as bare digit strings
                # (e.g. '42'), but form fields are named 'question_42'.
                # Only remap when the entry is not a known built-in field.
                if name not in builtin_names and name not in self.fields:
                    question_name = f'question_{name}'
                    if question_name in self.fields:
                        name = question_name
                    else:
                        logger.warning(
                            'fields_config[%s] entry %r does not match '
                            'any form field; skipping.',
                            config_key, name,
                        )
                        continue

                if name in self.fields and name not in configured_names:
                    configured_names.append(name)

            if configured_names:
                # Preserve any fields not mentioned in the configuration at the end
                remaining = [n for n in self.fields if n not in configured_names]
                self.order_fields(configured_names + remaining)


class ScheduledAtValidationMixin:
    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data.get('scheduled_at')
        if getattr(self, 'draft_save', False):
            return scheduled_at
        if scheduled_at is not None:
            if timezone.is_naive(scheduled_at):
                scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())
            buffer = timedelta(minutes=1)
            if scheduled_at < timezone.now() - buffer:
                raise forms.ValidationError(
                    _('Scheduled time must not be in the past.')
                )
        return scheduled_at
