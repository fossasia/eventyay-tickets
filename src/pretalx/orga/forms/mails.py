from django import forms

from pretalx.common.forms import ReadOnlyFlag
from pretalx.mail.models import MailTemplate


class MailTemplateForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = MailTemplate
        fields = [
            'subject', 'text', 'reply_to', 'log_address', 'bcc'
        ]
