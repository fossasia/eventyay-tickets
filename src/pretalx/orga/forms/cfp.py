from django import forms
from django.utils.translation import ugettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.fields import I18nFormField, I18nTextarea
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.phrases import phrases
from pretalx.submission.models import AnswerOption, CfP, Question, SubmissionType


class CfPSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    cfp_show_deadline = forms.BooleanField(
        label=_('Display deadline publicly'), required=False
    )
    cfp_request_abstract = forms.BooleanField(
        label=_('Offer data entry'), required=False
    )
    cfp_request_description = forms.BooleanField(
        label=_('Offer data entry'), required=False
    )
    cfp_request_notes = forms.BooleanField(label=_('Offer data entry'), required=False)
    cfp_request_biography = forms.BooleanField(
        label=_('Offer data entry'), required=False
    )
    cfp_request_do_not_record = forms.BooleanField(
        label=_('Offer data entry'), required=False
    )
    cfp_request_image = forms.BooleanField(label=_('Offer data entry'), required=False)
    cfp_require_abstract = forms.BooleanField(
        label=_('Force data entry'), required=False
    )
    cfp_require_description = forms.BooleanField(
        label=_('Force data entry'), required=False
    )
    cfp_require_notes = forms.BooleanField(label=_('Force data entry'), required=False)
    cfp_require_biography = forms.BooleanField(required=False)
    cfp_require_image = forms.BooleanField(label=_('Force data entry'), required=False)
    cfp_abstract_min_length = forms.IntegerField(
        label=_('Minimum length'), required=False, min_value=0
    )
    cfp_description_min_length = forms.IntegerField(
        label=_('Minimum length'), required=False, min_value=0
    )
    cfp_biography_min_length = forms.IntegerField(
        label=_('Minimum length'), required=False, min_value=0
    )
    cfp_abstract_max_length = forms.IntegerField(
        label=_('Maximum length'), required=False, min_value=0
    )
    cfp_description_max_length = forms.IntegerField(
        label=_('Maximum length'), required=False, min_value=0
    )
    cfp_biography_max_length = forms.IntegerField(
        label=_('Maximum length'), required=False, min_value=0
    )
    review_deadline = forms.DateTimeField(label=_('Review deadline'), required=False)
    review_score_mandatory = forms.BooleanField(
        label=_('Force data entry'), required=False
    )
    review_text_mandatory = forms.BooleanField(
        label=_('Force data entry'), required=False
    )
    mail_on_new_submission = forms.BooleanField(
        label=_('Send mail on new submission'),
        help_text=_(
            'If this setting is checked, you will receive an email to the organiser address for every received submission.'
        ),
        required=False,
    )
    allow_override_votes = forms.BooleanField(
        label=_('Allow override votes'),
        help_text=_(
            'Review teams can be assigned a fixed amount of "override votes": Positive or negative vetos each reviewer can assign.'
        ),
        required=False,
    )
    review_min_score = forms.IntegerField(
        label=_('Minimum score'), help_text=_('The minimum score reviewers can assign')
    )
    review_max_score = forms.IntegerField(
        label=_('Maximum score'), help_text=_('The maximum score reviewers can assign')
    )
    review_help_text = I18nFormField(
        label=_('Help text for reviewers'),
        help_text=_(
            'This text will be shown at the top of every review, as long as reviews can be created or edited.'
        )
        + ' '
        + phrases.base.use_markdown,
        widget=I18nTextarea,
        required=False,
    )

    def __init__(self, obj, *args, **kwargs):
        kwargs.pop(
            'read_only'
        )  # added in ActionFromUrl view mixin, but not needed here.
        super().__init__(*args, obj=obj, **kwargs)
        if getattr(obj, 'email'):
            self.fields[
                'mail_on_new_submission'
            ].help_text += f' (<a href="mailto:{obj.email}">{obj.email}</a>)'
        if getattr(obj, 'slug'):
            additional = _(
                'You can configure override votes <a href="{link}">in the team settings</a>.'
            ).format(link=obj.orga_urls.team_settings)
            self.fields['allow_override_votes'].help_text += f' {additional}'
        minimum = int(obj.settings.review_min_score)
        maximum = int(obj.settings.review_max_score)
        self.fields['review_deadline'].widget = forms.DateTimeInput(
            attrs={'class': 'datetimepickerfield'}
        )
        for number in range(abs(maximum - minimum + 1)):
            index = minimum + number
            self.fields[f'review_score_name_{index}'] = forms.CharField(
                label=_('Score label ({})').format(index),
                help_text=_(
                    'Human readable explanation of what a score of "{}" actually means, e.g. "great!".'
                ).format(index),
                required=False,
            )
        for field in ['abstract', 'description', 'biography']:
            self.fields[f'cfp_{field}_min_length'].widget.attrs['placeholder'] = ''
            self.fields[f'cfp_{field}_max_length'].widget.attrs['placeholder'] = ''

    def clean(self):
        data = self.cleaned_data
        minimum = int(data.get('review_min_score'))
        maximum = int(data.get('review_max_score'))
        if not minimum < maximum:
            raise forms.ValidationError(
                _('Please assign a minimum score smaller than the maximum score!')
            )
        return data


class CfPForm(ReadOnlyFlag, I18nModelForm):
    class Meta:
        model = CfP
        fields = ['headline', 'text', 'deadline']
        widgets = {
            'deadline': forms.DateTimeInput(attrs={'class': 'datetimepickerfield'})
        }


class QuestionForm(ReadOnlyFlag, I18nModelForm):
    class Meta:
        model = Question
        fields = [
            'target',
            'question',
            'help_text',
            'variant',
            'required',
            'contains_personal_data',
            'min_length',
            'max_length',
        ]


class AnswerOptionForm(ReadOnlyFlag, I18nModelForm):
    class Meta:
        model = AnswerOption
        fields = ['answer']


class SubmissionTypeForm(ReadOnlyFlag, I18nModelForm):
    class Meta:
        model = SubmissionType
        fields = ['name', 'default_duration', 'deadline']
        widgets = {
            'deadline': forms.DateTimeInput(attrs={'class': 'datetimepickerfield'})
        }
