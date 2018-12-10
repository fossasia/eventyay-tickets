from django import forms
from django.utils.translation import ugettext as _

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
            self.fields['speaker'] = forms.CharField(
                help_text=_(
                    'The email address of the speaker holding the talk. They will be invited to create an account.'
                )
            )
            self.fields['speaker_name'] = forms.CharField(
                help_text=_(
                    'The name of the speaker that should be displayed publicly.'
                )
            )
        if 'abstract' in self.fields:
            self.fields['abstract'].widget.attrs['rows'] = 2

        if not event.settings.use_tracks:
            self.fields.pop('track')
        else:
            self.fields['track'].queryset = event.tracks.all()

    class Meta:
        model = Submission
        fields = [
            'title',
            'submission_type',
            'track',
            'abstract',
            'description',
            'notes',
            'content_locale',
            'do_not_record',
            'duration',
            'image',
            'is_featured',
        ]
        request_require = {'abstract', 'description', 'notes', 'image', 'do_not_record'}
