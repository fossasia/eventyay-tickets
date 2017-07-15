from django import forms

from pretalx.common.forms import ReadOnlyFlag
from pretalx.submission.models import Submission, SubmissionType


class SubmissionForm(ReadOnlyFlag, forms.ModelForm):

    def __init__(self, event, **kwargs):
        super().__init__(**kwargs)
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(event=event)

    class Meta:
        model = Submission
        fields = [
            'title', 'submission_type', 'description', 'abstract',
            'notes', 'do_not_record', 'duration',
        ]
