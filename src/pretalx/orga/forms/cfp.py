from django import forms
from django.utils.translation import ugettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.submission.models import AnswerOption, CfP, Question, SubmissionType, Track


class CfPSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    use_tracks = forms.BooleanField(
        label=_('Use tracks'),
        required=False,
        help_text=_('Do you organise your talks by tracks?'),
    )
    allow_slot_count = forms.BooleanField(
        label=_('Slot Count'),
        required=False,
        help_text=_('Allow talks to be held multiple times?'),
    )
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
    cfp_request_availabilities = forms.BooleanField(
        label=_('Offer data entry'), required=False
    )
    cfp_request_do_not_record = forms.BooleanField(
        label=_('Offer data entry'), required=False
    )
    cfp_request_image = forms.BooleanField(label=_('Offer data entry'), required=False)
    cfp_request_track = forms.BooleanField(label=_('Offer data entry'), required=False)
    cfp_require_abstract = forms.BooleanField(
        label=_('Force data entry'), required=False
    )
    cfp_require_description = forms.BooleanField(
        label=_('Force data entry'), required=False
    )
    cfp_require_notes = forms.BooleanField(label=_('Force data entry'), required=False)
    cfp_require_biography = forms.BooleanField(required=False)
    cfp_require_availabilities = forms.BooleanField(required=False)
    cfp_require_image = forms.BooleanField(label=_('Force data entry'), required=False)
    cfp_require_track = forms.BooleanField(label=_('Force data entry'), required=False)
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
    cfp_count_length_in = forms.ChoiceField(
        label=_('Count text length in'),
        choices=(('chars', _('Characters')), ('words', _('Words'))),
    )
    mail_on_new_submission = forms.BooleanField(
        label=_('Send mail on new submission'),
        help_text=_(
            'If this setting is checked, you will receive an email to the organiser address for every received submission.'
        ),
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
        for field in ['abstract', 'description', 'biography']:
            self.fields[f'cfp_{field}_min_length'].widget.attrs['placeholder'] = ''
            self.fields[f'cfp_{field}_max_length'].widget.attrs['placeholder'] = ''


class CfPForm(ReadOnlyFlag, I18nModelForm):
    class Meta:
        model = CfP
        fields = ['headline', 'text', 'deadline']
        widgets = {
            'deadline': forms.DateTimeInput(attrs={'class': 'datetimepickerfield'})
        }


class QuestionForm(ReadOnlyFlag, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if not (
            event.settings.use_tracks
            and event.tracks.all().count()
            and event.settings.cfp_request_track
        ):
            self.fields.pop('tracks')
        else:
            self.fields['tracks'].queryset = event.tracks.all()
        if (
            instance
            and instance.pk
            and instance.answers.count()
            and not instance.is_public
        ):
            self.fields['is_public'].disabled = True

    class Meta:
        model = Question
        fields = [
            'target',
            'question',
            'help_text',
            'variant',
            'is_public',
            'required',
            'tracks',
            'contains_personal_data',
            'min_length',
            'max_length',
        ]


class AnswerOptionForm(ReadOnlyFlag, I18nModelForm):
    class Meta:
        model = AnswerOption
        fields = ['answer']


class SubmissionTypeForm(ReadOnlyFlag, I18nModelForm):
    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        if instance.pk and 'duration' in self.changed_data:
            instance.update_duration()

    class Meta:
        model = SubmissionType
        fields = ['name', 'default_duration', 'deadline']
        widgets = {
            'deadline': forms.DateTimeInput(attrs={'class': 'datetimepickerfield'})
        }


class TrackForm(ReadOnlyFlag, I18nModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['color'].widget.attrs['class'] = 'colorpickerfield'

    class Meta:
        model = Track
        fields = ['name', 'color']
