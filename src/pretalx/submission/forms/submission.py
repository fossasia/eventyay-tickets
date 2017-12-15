from django import forms
from django.conf import settings

from pretalx.submission.models import Submission, SubmissionType


class InfoForm(forms.ModelForm):

    def __init__(self, event, **kwargs):
        self.event = event
        readonly = kwargs.pop('readonly', False)

        super().__init__(**kwargs)
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(event=self.event)
        self.initial['submission_type'] = self.event.cfp.default_type
        locale_names = dict(settings.LANGUAGES)
        self.fields['content_locale'].choices = [(a, locale_names[a]) for a in self.event.locales]
        if readonly:
            for f in self.fields.values():
                f.disabled = True

    class Meta:
        model = Submission
        fields = [
            'title', 'submission_type', 'content_locale', 'abstract',
            'description', 'notes', 'do_not_record',
        ]
