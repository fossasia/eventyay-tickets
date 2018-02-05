from django import forms
from django.utils.translation import ugettext as _

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.submission.models import Submission, SubmissionType


class SubmissionForm(ReadOnlyFlag, forms.ModelForm):

    def __init__(self, event, **kwargs):
        super().__init__(**kwargs)
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(event=event)
        self.fields['title'].widget.attrs['placeholder'] = _('This is a serious talk')
        self.fields['abstract'].widget.attrs['placeholder'] = _('I am going to go into serious detail.')
        self.fields['description'].widget.attrs['placeholder'] = _(
            'In my opinion, there is too much frivolity and chaos in the world. '
            'This is why I feel we should concentrate on seriousness, as the '
            'Serious Conference always does. I will detail good methods to '
            'introduce seriousness in silly places.'
        )
        self.fields['notes'].widget.attrs['placeholder'] = _('I am a well-known speaker on this topic.')

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
