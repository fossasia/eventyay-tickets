from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.forms import ReadOnlyFlag
from pretalx.event.models import Event


class EventForm(ReadOnlyFlag, I18nModelForm):
    locales = forms.MultipleChoiceField(
        label=_('Active languages'),
        choices=settings.LANGUAGES,
        widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['locales'] = self.instance.locale_array.split(",")

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        qs = Event.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(_('This slug is already taken.'))

        return slug.lower()

    def clean(self):
        data = super().clean()

        if data.get('locale') not in data.get('locales'):
            raise forms.ValidationError(_('Your default language needs to be one of your active languages.'))
        if not data.get('email'):
            raise forms.ValidationError(_('Please provide a contact address – your speakers and participants should be able to reach you easily.'))

        return data

    def save(self, *args, **kwargs):
        self.instance.locale_array = ",".join(self.cleaned_data['locales'])
        return super().save(*args, **kwargs)

    class Meta:
        model = Event
        fields = [
            'name', 'slug', 'is_public', 'date_from', 'date_to', 'timezone',
            'email', 'locale', 'custom_css',
        ]
        widgets = {
            'date_from': forms.DateInput(attrs={'class': 'datepickerfield'}),
            'date_to': forms.DateInput(attrs={'class': 'datepickerfield',
                                              'data-date-after': '#id_date_from'}),
        }


class MailSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    mail_from = forms.EmailField(
        label=_("Sender address"),
        help_text=_("Sender address for outgoing emails")
    )
    smtp_use_custom = forms.BooleanField(
        label=_("Use custom SMTP server"),
        help_text=_("All mail related to your event will be sent over the smtp server specified by you."),
        required=False
    )
    smtp_host = forms.CharField(
        label=_("Hostname"),
        required=False
    )
    smtp_port = forms.IntegerField(
        label=_("Port"),
        required=False
    )
    smtp_username = forms.CharField(
        label=_("Username"),
        required=False
    )
    smtp_password = forms.CharField(
        label=_("Password"),
        required=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password'  # see https://bugs.chromium.org/p/chromium/issues/detail?id=370363#c7
        }),
    )
    smtp_use_tls = forms.BooleanField(
        label=_("Use STARTTLS"),
        help_text=_("Commonly enabled on port 587."),
        required=False
    )
    smtp_use_ssl = forms.BooleanField(
        label=_("Use SSL"),
        help_text=_("Commonly enabled on port 465."),
        required=False
    )

    def clean(self):
        data = self.cleaned_data
        if not data.get('smtp_password') and data.get('smtp_username'):
            # Leave password unchanged if the username is set and the password field is empty.
            # This makes it impossible to set an empty password as long as a username is set, but
            # Python's smtplib does not support password-less schemes anyway.
            data['smtp_password'] = self.initial.get('smtp_password')

        if data.get('smtp_use_tls') and data.get('smtp_use_ssl'):
            raise ValidationError(_('You can activate either SSL or STARTTLS security, but not both at the same time.'))
