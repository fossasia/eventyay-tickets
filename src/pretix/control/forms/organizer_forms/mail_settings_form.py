from django import forms
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _, pgettext_lazy
from i18nfield.forms import I18nFormField, I18nTextarea, I18nTextInput

from pretix.base.forms import (
    I18nMarkdownTextarea, PlaceholderValidator, SettingsForm,
)
from pretix.base.settings import PERSON_NAME_SCHEMES
from pretix.control.forms import SMTPSettingsMixin
from pretix.control.forms.event import multimail_validate
from pretix.multidomain.urlreverse import build_absolute_uri


class MailSettingsForm(SMTPSettingsMixin, SettingsForm):
    auto_fields = [
        'mail_from',
        'mail_from_name',
    ]

    mail_bcc = forms.CharField(
        label=_("Bcc address"),
        help_text=_("All your emails will be sent to this address as a Bcc copy"),
        validators=[multimail_validate],
        required=False,
        max_length=255
    )
    mail_text_signature = I18nFormField(
        label=_("Signature"),
        required=False,
        widget=I18nTextarea,
        help_text=_("This signature will be send along with all your email."),
        validators=[PlaceholderValidator([])],
        widget_kwargs={'attrs': {
            'rows': '4',
            'placeholder': _(
                'e.g. your contact details'
            )
        }}
    )

    mail_text_customer_registration = I18nFormField(
        label=_("Text"),
        required=False,
        widget=I18nMarkdownTextarea,
    )
    mail_subject_customer_registration = I18nFormField(
        label=_("Subject"),
        required=False,
        widget=I18nTextInput,
    )
    mail_text_customer_email_change = I18nFormField(
        label=_("Text"),
        required=False,
        widget=I18nTextInput,
    )
    mail_text_customer_reset = I18nFormField(
        label=_("Text"),
        required=False,
        widget=I18nTextInput,
    )

    mail_subject_customer_email_change = I18nFormField(
        label=_("Subject"),
        required=False,
        widget=I18nTextInput,
    )

    mail_subject_customer_reset = I18nFormField(
        label=_("Subject"),
        required=False,
        widget=I18nTextInput,
    )

    base_context = {
        'mail_text_customer_registration': ['customer', 'url'],
        'mail_subject_customer_registration': ['customer', 'url'],
        'mail_text_customer_email_change': ['customer', 'url'],
        'mail_subject_customer_email_change': ['customer', 'url'],
        'mail_text_customer_reset': ['customer', 'url'],
        'mail_subject_customer_reset': ['customer', 'url'],
    }

    def _get_sample_context(self, base_parameters):
        placeholders = {
            'organizer': self.organizer.name
        }

        if 'url' in base_parameters:
            token = get_random_string(30)
            placeholders[
                'url'] = f"{build_absolute_uri(self.organizer, 'presale:organizer.customer.activate')}?token={token}"

        if 'customer' in base_parameters:
            placeholders['name'] = pgettext_lazy('person_name_sample', 'John Doe')
            name_scheme = PERSON_NAME_SCHEMES[self.organizer.settings.name_scheme]
            for f, l, w in name_scheme['fields']:
                if f == 'full_name':
                    continue
                placeholders['name_%s' % f] = name_scheme['sample'][f]
        return placeholders

    def _set_field_placeholders(self, fn, base_parameters):
        phs = [
            '{%s}' % p
            for p in sorted(self._get_sample_context(base_parameters).keys())
        ]
        ht = _('Available placeholders: {list}').format(
            list=', '.join(phs)
        )
        if self.fields[fn].help_text:
            self.fields[fn].help_text += ' ' + str(ht)
        else:
            self.fields[fn].help_text = ht
        self.fields[fn].validators.append(
            PlaceholderValidator(phs)
        )

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.get('obj')
        super().__init__(*args, **kwargs)
        for k, v in self.base_context.items():
            self._set_field_placeholders(k, v)
