from django import forms
from i18nfield.forms import I18nModelForm

from pretalx.common.forms import ReadOnlyFlag
from pretalx.submission.models import CfP, Question, SubmissionType


class CfPForm(ReadOnlyFlag, I18nModelForm):

    class Meta:
        model = CfP
        fields = [
            'headline', 'text', 'deadline',
        ]


class QuestionForm(ReadOnlyFlag, I18nModelForm):

    class Meta:
        model = Question
        fields = [
            'question', 'variant', 'default_answer', 'required',
        ]


class SubmissionTypeForm(ReadOnlyFlag, I18nModelForm):

    class Meta:
        model = SubmissionType
        fields = [
            'name', 'default_duration', 'max_duration',
        ]
