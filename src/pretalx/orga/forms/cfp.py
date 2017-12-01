from django import forms
from django.utils.translation import ugettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.phrases import phrases
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['headline'].widget.attrs['placeholder'] = _('The Call for Participation for this year\'s Serious Conference is open!')
        self.fields['text'].widget.attrs['placeholder'] = _(
            'Join us in this year\'s serious conference with fascinating discussions '
            'on **Serious Business Matters**! '
            'We accept short-form and long-form talks, as well as workshops '
            'on our greatest serious achievements. Know details about how to '
            'manage serious companies? Were you working on a seriously serious '
            'project? We want your expertise!'
        )

    class Meta:
        model = CfP
        fields = [
            'headline', 'text', 'deadline',
        ]
        widgets = {
            'deadline': forms.DateTimeInput(attrs={'class': 'datetimepickerfield'})
        }


class QuestionForm(ReadOnlyFlag, I18nModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['question'].widget.attrs['placeholder'] = _('What kind of dessert do you prefer?')
        self.fields['help_text'].widget.attrs['placeholder'] = _('Please include things you will not eat at all, too.')

    class Meta:
        model = Question
        fields = [
            'target', 'question', 'help_text', 'variant', 'required',
            'contains_personal_data',
        ]


class AnswerOptionForm(ReadOnlyFlag, I18nModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['answer'].widget.attrs['placeholder'] = phrases.orga.example_answer

    class Meta:
        model = AnswerOption
        fields = [
            'answer',
        ]


class SubmissionTypeForm(ReadOnlyFlag, I18nModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['placeholder'] = _('Long talk')

    class Meta:
        model = SubmissionType
        fields = [
            'name', 'default_duration', 'max_duration',
        ]
