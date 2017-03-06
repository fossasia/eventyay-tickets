from django import forms
from django.utils.timezone import get_current_timezone_name

from pretalx.common.forms import ReadOnlyFlag
from pretalx.person.models import EventPermission, User
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
