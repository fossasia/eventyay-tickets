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
        self.fields['headline'].widget.attrs['placeholder'] = _('The Call for Participation for this year\'s senate is open!')
        self.fields['text'].widget.attrs['placeholder'] = _(
            'Join us in this year\'s senate with fascinating discussions on '
            'the **Public Good**! '
            'We accept short-form and long-form speeches, as well as workshops '
            'on our greatest military achievements. Know details about how to '
            'build walls? Were you working with Hadrian, or stationed at the '
            'Lîmes? We want your expertise!'
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
        self.fields['question'].widget.attrs['placeholder'] = _('What have the Romans ever done for us?')
        self.fields['help_text'].widget.attrs['placeholder'] = _('Please give an exhaustive list of your view on Rome\'s most impressive achievements.')

    class Meta:
        model = Question
        fields = [
            'target', 'question', 'help_text', 'variant', 'required', 'active',
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
        self.fields['name'].widget.attrs['placeholder'] = _('Long speech')

    class Meta:
        model = SubmissionType
        fields = [
            'name', 'default_duration', 'max_duration',
        ]
