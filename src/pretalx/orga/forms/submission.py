from django import forms
from django.utils.translation import ugettext as _
from django_scopes.forms import SafeModelChoiceField

from pretalx.common.mixins.forms import ReadOnlyFlag, RequestRequire
from pretalx.submission.models import Submission, SubmissionType


class SubmissionForm(ReadOnlyFlag, RequestRequire, forms.ModelForm):
    def __init__(self, event, **kwargs):
        self.event = event
        super().__init__(**kwargs)
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(
            event=event
        )

        if not self.instance.pk:
            self.fields['speaker'] = forms.EmailField(
                label=_('Speaker email'),
                help_text=_(
                    'The email address of the speaker holding the talk. They will be invited to create an account.'
                )
            )
            self.fields['speaker_name'] = forms.CharField(
                label=_('Speaker name'),
                help_text=_(
                    'The name of the speaker that should be displayed publicly.'
                )
            )
        if 'abstract' in self.fields:
            self.fields['abstract'].widget.attrs['rows'] = 2
        if not event.settings.present_multiple_times:
            self.fields.pop('slot_count')
        if not event.settings.use_tracks:
            self.fields.pop('track')
        else:
            self.fields['track'].queryset = event.tracks.all()

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        if instance.pk and 'duration' in self.changed_data:
            instance.update_duration()
        if 'slot_count' in self.changed_data and 'slot_count' in self.initial:
            instance.update_talk_slots()
        return instance

    class Meta:
        model = Submission
        fields = [
            'title',
            'submission_type',
            'track',
            'abstract',
            'description',
            'notes',
            'internal_notes',
            'content_locale',
            'do_not_record',
            'duration',
            'slot_count',
            'image',
            'is_featured',
        ]
        field_classes = {
            'submission_type': SafeModelChoiceField,
            'track': SafeModelChoiceField,
        }
        request_require = {'abstract', 'description', 'notes', 'image', 'do_not_record'}
