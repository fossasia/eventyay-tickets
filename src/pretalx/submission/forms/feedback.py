from django import forms
from django.utils.translation import ugettext as _

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.submission.models import Feedback


class FeedbackForm(ReadOnlyFlag, forms.ModelForm):
    def __init__(self, talk, **kwargs):
        super().__init__(**kwargs)
        self.instance.talk = talk
        self.fields['speaker'].queryset = self.instance.talk.speakers.all()
        self.fields['speaker'].empty_label = _('All speakers')

    def save(self, *args, **kwargs):
        if not self.cleaned_data['speaker'] and self.instance.talk.speakers.count() == 1:
            self.instance.speaker = self.instance.talk.speakers.first()
        return super().save(*args, **kwargs)

    class Meta:
        model = Feedback
        fields = [
            'speaker', 'review',
        ]
