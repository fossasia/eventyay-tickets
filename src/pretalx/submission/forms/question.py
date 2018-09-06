from decimal import Decimal

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.functional import cached_property

from pretalx.common.forms.utils import get_help_text
from pretalx.submission.models import Answer, Question, QuestionTarget, QuestionVariant


class QuestionsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        self.submission = kwargs.pop('submission', None)
        self.speaker = kwargs.pop('speaker', None)
        self.review = kwargs.pop('review', None)
        self.request_user = kwargs.pop('request_user', None)
        self.target_type = kwargs.pop('target', QuestionTarget.SUBMISSION)
        target_object = None
        if self.target_type == QuestionTarget.SUBMISSION:
            target_object = self.submission
        elif self.target_type == QuestionTarget.SPEAKER:
            target_object = self.speaker
        elif self.target_type == QuestionTarget.REVIEWER:
            target_object = self.review
        readonly = kwargs.pop('readonly', False)

        super().__init__(*args, **kwargs)

        self.queryset = Question.all_objects.filter(event=self.event, active=True)
        if self.target_type:
            self.queryset = self.queryset.filter(target=self.target_type)
        else:
            self.queryset = self.queryset.exclude(target=QuestionTarget.REVIEWER)
        for question in self.queryset.prefetch_related('options'):
            if target_object:
                answers = [
                    a
                    for a in target_object.answers.all()
                    if a.question_id == question.id
                ]
                if answers:
                    initial_object = answers[0]
                    initial = (
                        answers[0].answer_file
                        if question.variant == QuestionVariant.FILE
                        else answers[0].answer
                    )
                else:
                    initial_object = None
                    initial = question.default_answer
            else:
                initial_object = None
                initial = question.default_answer

            field = self.get_field(
                question=question,
                initial=initial,
                initial_object=initial_object,
                readonly=readonly,
            )
            field.question = question
            field.answer = initial_object
            self.fields[f'question_{question.pk}'] = field

    @cached_property
    def speaker_fields(self):
        return [
            forms.BoundField(self, field, name)
            for name, field in self.fields.items()
            if field.question.target == QuestionTarget.SPEAKER
        ]

    @cached_property
    def submission_fields(self):
        return [
            forms.BoundField(self, field, name)
            for name, field in self.fields.items()
            if field.question.target == QuestionTarget.SUBMISSION
        ]

    def get_field(self, *, question, initial, initial_object, readonly):
        if question.variant == QuestionVariant.BOOLEAN:
            # For some reason, django-bootstrap4 does not set the required attribute
            # itself.
            widget = (
                forms.CheckboxInput(attrs={'required': 'required'})
                if question.required
                else forms.CheckboxInput()
            )
            initialbool = (
                (initial == 'True') if initial else bool(question.default_answer)
            )

            return forms.BooleanField(
                disabled=readonly,
                help_text=question.help_text,
                label=question.question,
                required=question.required,
                widget=widget,
                initial=initialbool,
            )
        elif question.variant == QuestionVariant.NUMBER:
            return forms.DecimalField(
                disabled=readonly,
                help_text=question.help_text,
                label=question.question,
                required=question.required,
                min_value=Decimal('0.00'),
                initial=initial,
            )
        elif question.variant == QuestionVariant.STRING:
            return forms.CharField(
                disabled=readonly,
                help_text=get_help_text(
                    question.help_text, question.min_length, question.max_length
                ),
                label=question.question,
                required=question.required,
                initial=initial,
                min_length=question.min_length,
                max_length=question.max_length,
            )
        elif question.variant == QuestionVariant.TEXT:
            return forms.CharField(
                label=question.question,
                required=question.required,
                widget=forms.Textarea,
                disabled=readonly,
                help_text=get_help_text(
                    question.help_text, question.min_length, question.max_length
                ),
                initial=initial,
                min_length=question.min_length,
                max_length=question.max_length,
            )
        elif question.variant == QuestionVariant.FILE:
            return forms.FileField(
                label=question.question,
                required=question.required,
                disabled=readonly,
                help_text=question.help_text,
                initial=initial,
            )
        elif question.variant == QuestionVariant.CHOICES:
            return forms.ModelChoiceField(
                queryset=question.options.all(),
                label=question.question,
                required=question.required,
                initial=initial_object.options.first()
                if initial_object
                else question.default_answer,
                disabled=readonly,
                help_text=question.help_text,
            )
        elif question.variant == QuestionVariant.MULTIPLE:
            return forms.ModelMultipleChoiceField(
                queryset=question.options.all(),
                label=question.question,
                required=question.required,
                widget=forms.CheckboxSelectMultiple,
                initial=initial_object.options.all()
                if initial_object
                else question.default_answer,
                disabled=readonly,
                help_text=question.help_text,
            )

    def save(self):
        for k, v in self.cleaned_data.items():
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
                # Not distinguishing between the external question types helps to make
                # experiences smoother if orga changes a question type.
                answer = Answer(
                    review=self.review,
                    submission=self.submission,
                    person=self.speaker,
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
