from django import forms
from django.utils.translation import ugettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.mail.context import get_context_explanation
from pretalx.mail.models import MailTemplate, QueuedMail
from pretalx.person.models import User


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
                t
                for t in self.instance.event.fixed_templates
                if t != self.event.update_template
            ]
            if _is_template_with_submission_context:
                context = {item['name']: 'test' for item in get_context_explanation()}
                try:
                    for language, local_text in text.data.items():
                        local_text.format(**context)
                except KeyError as e:
                    msg = _('Unknown template key: "{key}", locale: {locale}').format(
                        key=e.args[0], locale=language
                    )
                    raise forms.ValidationError(msg)
        return text

    class Meta:
        model = MailTemplate
        fields = ['subject', 'text', 'reply_to', 'bcc']


class MailDetailForm(ReadOnlyFlag, forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.to_users.all().count():
            self.fields.pop('to_users')
        else:
            self.fields['to_users'].queryset = self.instance.to_users.all()
            self.fields['to_users'].required = False

    def clean(self, *args, **kwargs):
        cleaned_data = super().clean(*args, **kwargs)
        if not cleaned_data['to'] and not cleaned_data.get('to_users'):
            self.add_error('to', forms.ValidationError(_('An email needs to have at least one recipient.')))
        return cleaned_data

    def save(self, *args, **kwargs):
        obj = super().save(*args, **kwargs)
        if self.has_changed() and 'to' in self.changed_data:
            addresses = list(set(a.strip().lower() for a in (obj.to or '').split(',') if a.strip()))
            for address in addresses:
                user = User.objects.filter(email__iexact=address).first()
                if user:
                    addresses.remove(address)
                    obj.to_users.add(user)
            addresses = ','.join(addresses) if addresses else ''
            obj.to = addresses
            obj.save()
        return obj

    class Meta:
        model = QueuedMail
        fields = ['to', 'to_users', 'reply_to', 'cc', 'bcc', 'subject', 'text']
        widgets = {'to_users': forms.CheckboxSelectMultiple}


class WriteMailForm(forms.ModelForm):
    recipients = forms.MultipleChoiceField(
        label=_('Recipient groups'),
        choices=(
            (
                'submitted',
                _(
                    'Everyone with submission(s) that have not been accepted/rejected yet'
                ),
            ),
            (
                'accepted',
                _('All accepted speakers (who have not confirmed their talk yet)'),
            ),
            ('confirmed', _('All confirmed speakers')),
            ('rejected', _('All rejected speakers')),
            (
                'selected_submissions',
                _('All speakers of the selected submissions below'),
            ),
            ('reviewers', _('All reviewers in your team')),
        ),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    additional_recipients = forms.CharField(
        label=_('Recipients'),
        required=False,
        help_text=_('One email address or several addresses separated by commas.'),
    )
    submissions = forms.MultipleChoiceField(required=False)
    reply_to = forms.CharField(required=False)

    def __init__(self, event, **kwargs):
        super().__init__(**kwargs)
        self.fields['submissions'].choices = [
            (sub.code, sub.title) for sub in event.submissions.all()
        ]
        self.fields['text'].help_text = _(
            'Please note: Placeholders will not be substituted, this is an upcoming feature. '
            'Leave no placeholders in this field.'
        )

    class Meta:
        model = QueuedMail
        fields = ['cc', 'bcc', 'subject', 'text']
