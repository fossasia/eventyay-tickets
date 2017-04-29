from decimal import Decimal

from django import forms

from pretalx import settings
from pretalx.submission.models import (
    QuestionVariant, Submission, SubmissionType,
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
            'title', 'submission_type', 'content_locale', 'description',
            'abstract', 'notes', 'do_not_record',
        ]


class QuestionsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        submission = kwargs.pop('submission', None)
        readonly = kwargs.pop('readonly', False)

        super().__init__(*args, **kwargs)

        for q in event.questions.prefetch_related('options'):
            if submission:
                answers = [a for a in submission.answers.all() if a.question_id == q.id]
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
            self.fields['question_%s' % q.id] = field
