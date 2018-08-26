from django import forms
from django.utils.translation import ugettext as _

from pretalx.common.forms.utils import get_help_text
from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.submission.models import Submission, SubmissionType


class SubmissionForm(ReadOnlyFlag, forms.ModelForm):
    def __init__(self, event, **kwargs):
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
        self.fields['abstract'].widget.attrs['rows'] = 2
        for key in {'abstract', 'description', 'notes', 'image', 'do_not_record'}:
            request = event.settings.get(f'cfp_request_{key}')
            require = event.settings.get(f'cfp_require_{key}')
            if not request:
                self.fields.pop(key)
            else:
                self.fields[key].required = require
                min_value = event.settings.get(f'cfp_{key}_min_length')
                max_value = event.settings.get(f'cfp_{key}_max_length')
                if min_value:
                    self.fields[key].widget.attrs[f'minlength'] = min_value
                if max_value:
                    self.fields[key].widget.attrs[f'maxlength'] = max_value
                self.fields[key].help_text = get_help_text(
                    self.fields[key].help_text, min_value, max_value
                )

    class Meta:
        model = Submission
        fields = [
            'title',
            'submission_type',
            'abstract',
            'description',
            'notes',
            'content_locale',
            'do_not_record',
            'duration',
            'image',
            'is_featured',
        ]
