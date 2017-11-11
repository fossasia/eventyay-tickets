from django import forms
from django.utils.translation import ugettext as _

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.submission.models import Submission, SubmissionType


class SubmissionForm(ReadOnlyFlag, forms.ModelForm):

    def __init__(self, event, **kwargs):
        super().__init__(**kwargs)
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(event=event)
        self.fields['title'].widget.attrs['placeholder'] = _('Should we destroy Catharge?')
        self.fields['abstract'].widget.attrs['placeholder'] = _('I think we should destroy Catharge.')
        self.fields['description'].widget.attrs['placeholder'] = _(
            'I think the situation in and around Catharge has gotten out of hand. '
            'We should definitely concentrate on annihilating Catharge, and I am '
            'prepared to hold many, many speeches on this topic.'
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
        ]
