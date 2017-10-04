from decimal import Decimal

from django import forms

from pretalx import settings
from pretalx.submission.models import (
    Answer, QuestionVariant, Submission, SubmissionType,
)


class InfoForm(forms.ModelForm):

    def __init__(self, event, **kwargs):
        self.event = event
        readonly = kwargs.pop('readonly', False)

        super().__init__(**kwargs)
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(event=self.event)
        locale_names = dict(settings.LANGUAGES)
        self.fields['content_locale'].choices = [(a, locale_names[a]) for a in self.event.locales]
        if readonly:
            for f in self.fields.values():
                f.disabled = True

    class Meta:
        model = Submission
        fields = [
            'title', 'submission_type', 'content_locale', 'abstract',
            'description', 'notes', 'do_not_record',
        ]


class QuestionsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        self.submission = kwargs.pop('submission', None)
        self.speaker = kwargs.pop('speaker', None)
        self.request_user = kwargs.pop('request_user', None)
        self.target_type = kwargs.pop('target', 'submission')
        target_object = self.submission or self.speaker if self.target_type else None
        readonly = kwargs.pop('readonly', False)

        super().__init__(*args, **kwargs)

        queryset = self.event.questions.all()
        if self.target_type:
            queryset = queryset.filter(target=self.target_type)
        for q in queryset.prefetch_related('options'):
            if target_object:
                answers = [a for a in target_object.answers.all() if a.question_id == q.id]
                if answers:
                    initial_obj = answers[0]
                    initial = answers[0].answer
                else:
                    initial_obj = None
                    initial = q.default_answer
            else:
                initial_obj = None
                initial = q.default_answer

            if q.variant == QuestionVariant.BOOLEAN:
                # For some reason, django-bootstrap4 does not set the required attribute
                # itself.
                widget = forms.CheckboxInput(attrs={'required': 'required'}) if q.required else forms.CheckboxInput()
                initialbool = (initial == 'True') if initial else bool(q.default_answer)

                field = forms.BooleanField(
                    disabled=readonly,
                    label=q.question, required=q.required,
                    widget=widget, initial=initialbool
                )
            elif q.variant == QuestionVariant.NUMBER:
                field = forms.DecimalField(
                    disabled=readonly,
                    label=q.question, required=q.required,
                    min_value=Decimal('0.00'), initial=initial
                )
            elif q.variant == QuestionVariant.STRING:
                field = forms.CharField(
                    disabled=readonly,
                    label=q.question, required=q.required, initial=initial
                )
            elif q.variant == QuestionVariant.TEXT:
                field = forms.CharField(
                    label=q.question, required=q.required,
                    widget=forms.Textarea,
                    disabled=readonly,
                    initial=initial
                )
            elif q.variant == QuestionVariant.CHOICES:
                field = forms.ModelChoiceField(
                    queryset=q.options.all(),
                    label=q.question, required=q.required,
                    widget=forms.RadioSelect,
                    initial=initial_obj.options.first() if initial_obj else q.default_answer,
                    disabled=readonly,
                )
            elif q.variant == QuestionVariant.MULTIPLE:
                field = forms.ModelMultipleChoiceField(
                    queryset=q.options.all(),
                    label=q.question, required=q.required,
                    widget=forms.CheckboxSelectMultiple,
                    initial=initial_obj.options.all() if initial_obj else q.default_answer,
                    disabled=readonly,
                )
            field.question = q
            field.answer = initial_obj
            self.fields[f'question_{q.pk}'] = field

    def save(self):
        for k, v in self.cleaned_data.items():
            field = self.fields[k]
            if field.answer:
                # We already have a cached answer object, so we don't
                # have to create a new one
                if v == '':
                    # TODO: Deleting the answer removes the option to have a log here.
                    # Maybe setting the answer to '' is the right way to go.
                    field.answer.delete()
                else:
                    self._save_to_answer(field, field.answer, v)
                    field.answer.save()
            elif v != '':
                # Not distinguishing between the question types helps to make
                # experiences smoother if orga changes a question type.
                answer = Answer(
                    submission=self.submission,
                    person=self.speaker,
                    question=field.question,
                )
                self._save_to_answer(field, answer, v)
                answer.save()

    def _save_to_answer(self, field, answer, value):
        action = 'pretalx.submission.answer' + ('update' if answer.pk else 'create')
        if isinstance(field, forms.ModelMultipleChoiceField):
            answstr = ', '.join([str(o) for o in value])
            if not answer.pk:
                answer.save()
            else:
                answer.options.clear()
            answer.answer = answstr
            answer.options.add(*value)
        elif isinstance(field, forms.ModelChoiceField):
            if not answer.pk:
                answer.save()
            else:
                answer.options.clear()
            answer.options.add(value)
            answer.answer = value.answer
        else:
            answer.answer = value
        answer.log_action(action, person=self.request_user, data={'answer': value})
