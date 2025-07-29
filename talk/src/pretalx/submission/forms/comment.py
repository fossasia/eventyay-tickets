from django import forms

from pretalx.common.forms.renderers import InlineFormRenderer
from pretalx.common.forms.widgets import MarkdownWidget
from pretalx.submission.models import SubmissionComment


class SubmissionCommentForm(forms.ModelForm):
    default_renderer = InlineFormRenderer

    class Meta:
        model = SubmissionComment
        fields = ("text",)
        widgets = {"text": MarkdownWidget}

    def __init__(self, *args, submission=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.submission = submission
        self.user = user

    def save(self, *args, **kwargs):
        self.instance.submission = self.submission
        self.instance.user = self.user
        instance = super().save(*args, **kwargs)
        instance.log_action(
            "pretalx.submission.comment.create", person=self.user, orga=True
        )
        return instance
