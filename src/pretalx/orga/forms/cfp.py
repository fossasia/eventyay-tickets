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
    allow_override_votes = forms.BooleanField(
        label=_('Allow override votes'),
        help_text=_('With this setting, individual reviewers can be assigned a fixed amount of "override votes" functioning like vetos.'),
        required=False,
    )
    review_min_score = forms.IntegerField(
        label=_('Minimum score'),
        help_text=_('The minimum score reviewers can assign'),
    )
    review_max_score = forms.IntegerField(
        label=_('Maximum score'),
        help_text=_('The maximum score reviewers can assign'),
    )

    def __init__(self, obj, *args, **kwargs):
        kwargs.pop('read_only')  # added in ActionFromUrl view mixin, but not needed here.
        super().__init__(*args, obj=obj, **kwargs)
        minimum = int(obj.settings.review_min_score)
        maximum = int(obj.settings.review_max_score)
        for number in range(abs(maximum - minimum + 1)):
            index = minimum + number
            self.fields[f'review_score_name_{index}'] = forms.CharField(
                label=_('Score label ({})').format(index),
                required=False
            )

    def clean(self):
        data = self.cleaned_data
        minimum = int(data.get('review_min_score'))
        maximum = int(data.get('review_max_score'))
        if not minimum < maximum:
            raise forms.ValidationError(_('Please assign a minimum score smaller than the maximum score!'))
        return data


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
            'name', 'default_duration', 'deadline',
        ]
        widgets = {
            'deadline': forms.DateTimeInput(attrs={'class': 'datetimepickerfield'})
        }
