from django import forms

from pretalx.common.forms import ReadOnlyFlag
from pretalx.submission.models import Submission


class SubmissionForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = Submission
        fields = [
            'title', 'subtitle', 'submission_type', 'description', 'abstract', 'notes', 'duration',
        ]
