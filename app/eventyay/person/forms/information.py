from django_scopes.forms import SafeModelMultipleChoiceField
from i18nfield.forms import I18nModelForm

from eventyay.common.forms.fields import SizeFileField
from eventyay.common.forms.mixins import I18nHelpText
from eventyay.common.forms.widgets import EnhancedSelectMultiple
from eventyay.base.models.information import SpeakerInformation


class SpeakerInformationForm(I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields['limit_types'].queryset = event.submission_types.all()
        if not event.get_feature_flag('use_tracks'):
            self.fields.pop('limit_tracks')
        else:
            self.fields['limit_tracks'].queryset = event.tracks.all()

    def save(self, *args, **kwargs):
        self.instance.event = self.event
        return super().save(*args, **kwargs)

    class Meta:
        model = SpeakerInformation
        fields = (
            'title',
            'text',
            'target_group',
            'limit_types',
            'limit_tracks',
            'resource',
        )
        field_classes = {
            'limit_tracks': SafeModelMultipleChoiceField,
            'limit_types': SafeModelMultipleChoiceField,
            'resource': SizeFileField,
        }
        widgets = {
            'limit_tracks': EnhancedSelectMultiple(color_field='color'),
            'limit_types': EnhancedSelectMultiple,
        }
