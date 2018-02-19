from django import forms
from django.utils.translation import ugettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.mail.context import get_context_explanation
from pretalx.mail.models import MailTemplate, QueuedMail


class MailTemplateForm(ReadOnlyFlag, I18nModelForm):

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        if event:
            kwargs['locales'] = event.locales
        super().__init__(*args, **kwargs)

    def clean_text(self):
        text = self.cleaned_data['text']
        if self.instance and self.instance.id:
            _is_template_with_submission_context = self.instance in [
                t for t in self.instance.event.fixed_templates if t != self.event.update_template
            ]
            if _is_template_with_submission_context:
                context = {item['name']: 'test' for item in get_context_explanation()}
                try:
                    for language, local_text in text.data.items():
                        local_text.format(**context)
                except KeyError as e:
                    msg = _('Unknown template key: "{key}", locale: {locale}').format(key=e.args[0], locale=language)
                    raise forms.ValidationError(msg)
        return text

    class Meta:
        model = MailTemplate
        fields = [
            'subject', 'text', 'reply_to', 'bcc',
        ]


class MailDetailForm(ReadOnlyFlag, forms.ModelForm):

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
