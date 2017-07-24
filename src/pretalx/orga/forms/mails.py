from django import forms
from django.utils.translation import ugettext_lazy as _

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


class WriteMailForm(forms.ModelForm):
    recipients = forms.MultipleChoiceField(choices=(
        ('submitted', _('Everyone with submission(s) that have not been accepted/rejected yet')),
        ('accepted', _('All accepted speakers (who have not confirmed their talk yet)')),
        ('confirmed', _('All confirmed speakers')),
        ('rejected', _('All rejected speakers')),
        ('selected_submissions', _('All speakers of the selected submissions below'))
    ), widget=forms.CheckboxSelectMultiple)
    submissions = forms.MultipleChoiceField(required=False)
    reply_to = forms.EmailField(required=False)

    def __init__(self, event, **kwargs):
        super().__init__(**kwargs)
        self.fields['submissions'].choices = [(sub.code, sub.title) for sub in event.submissions.all()]

    class Meta:
        model = QueuedMail
        fields = [
            'cc', 'bcc', 'subject', 'text',
        ]
