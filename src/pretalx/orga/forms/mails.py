from django import forms

from pretalx.common.forms import ReadOnlyFlag
from pretalx.mail.models import MailTemplate, QueuedMail


class MailTemplateForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = MailTemplate
        fields = [
            'subject', 'text', 'reply_to', 'bcc',
        ]


class OutboxMailForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = QueuedMail
        fields = [
            'to', 'reply_to', 'cc', 'bcc', 'subject', 'text',
        ]
