from django import forms

from pretalx.common.forms import ReadOnlyFlag
from pretalx.submission.models import CfP, Question, SubmissionType


class CfPForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = CfP
        fields = [
            'headline', 'text', 'deadline',
        ]


class QuestionForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = Question
        fields = [
            'question', 'variant', 'default_answer', 'required',
        ]


class SubmissionTypeForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = SubmissionType
        fields = [
            'name', 'default_duration', 'max_duration',
        ]
