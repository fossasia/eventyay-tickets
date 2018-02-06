from django import forms
from django.utils.translation import ugettext as _

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.submission.models import Submission, SubmissionType


class SubmissionForm(ReadOnlyFlag, forms.ModelForm):

    def __init__(self, event, **kwargs):
        super().__init__(**kwargs)
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(event=event)

        if not self.instance.pk:
            self.fields['speaker'] = forms.CharField(
                help_text=_('Add the email or nickname of the speaker holding the talk. They will be invited to create an account.')
            )

    class Meta:
        model = Submission
        fields = [
            'title', 'submission_type', 'abstract', 'description',
            'notes', 'content_locale', 'do_not_record', 'duration',
            'image',
        ]
