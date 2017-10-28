from django import forms
from django.utils.translation import ugettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.forms import ReadOnlyFlag
from pretalx.submission.models import (
    AnswerOption, CfP, Question, SubmissionType,
)


class CfPSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    cfp_show_deadline = forms.BooleanField(label=_('Display deadline publicly'),
                                           required=False)
    mail_on_new_submission = forms.BooleanField(
        label=_('Send mail on new submission'),
        help_text=_('If this setting is checked, you will receive an email to the orga address for every received submission.'),
        required=False
    )


class CfPForm(ReadOnlyFlag, I18nModelForm):

    class Meta:
        model = CfP
        fields = [
            'headline', 'text', 'deadline',
        ]
        widgets = {
            'deadline': forms.DateTimeInput(attrs={'class': 'datetimepickerfield'})
        }


class QuestionForm(ReadOnlyFlag, I18nModelForm):

    class Meta:
        model = Question
        fields = [
            'target', 'question', 'help_text', 'variant', 'required', 'active',
        ]


class AnswerOptionForm(ReadOnlyFlag, I18nModelForm):

    class Meta:
        model = AnswerOption
        fields = [
            'answer',
        ]


class SubmissionTypeForm(ReadOnlyFlag, I18nModelForm):

    class Meta:
        model = SubmissionType
        fields = [
            'name', 'default_duration', 'max_duration',
        ]
