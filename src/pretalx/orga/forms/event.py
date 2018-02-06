from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.css import validate_css
from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.event.models import Event
from pretalx.orga.forms.widgets import HeaderSelect


class EventForm(ReadOnlyFlag, I18nModelForm):
    locales = forms.MultipleChoiceField(
        label=_('Active languages'),
        choices=settings.LANGUAGES,
        widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['locales'] = self.instance.locale_array.split(",")
        if not self.instance or not self.instance.pk:
            self.fields['is_public'].widget = forms.HiddenInput()
            self.fields['primary_color'].widget = forms.HiddenInput()
            self.fields['custom_css'].widget = forms.HiddenInput()

        year = str(now().year)
        self.fields['name'].widget.attrs['placeholder'] = _('The name of your conference, e.g. My Conference') + ' ' + year
        self.fields['slug'].widget.attrs['placeholder'] = _('A short version of your conference name, e.g. mycon') + year[2:]
        self.fields['primary_color'].widget.attrs['placeholder'] = _('A color hex value, e.g. #ab01de')
        if self.instance and self.instance.slug:
            self.fields['slug'].disabled = True

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        qs = Event.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(_('This short name is already taken, please choose another one (or ask the owner of that event to add you to their team).'))

        return slug.lower()

    def clean_custom_css(self, *args, **kwargs):
        def handle_missing_css():
            self.instance.custom_css = None
            if self.instance.pk:
                self.instance.save(update_fields=['custom_css'])

        if self.cleaned_data.get('custom_css') or self.files.get('custom_css'):
            css = self.cleaned_data['custom_css'] or self.files['custom_css']
            try:
                validate_css(css.read())
                return css
            except IsADirectoryError:
                handle_missing_css()
        else:
            handle_missing_css()

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
            'email', 'locale', 'primary_color', 'custom_css', 'logo',
            'landing_page_text',
        ]
        widgets = {
            'date_from': forms.DateInput(attrs={'class': 'datepickerfield'}),
            'date_to': forms.DateInput(attrs={'class': 'datepickerfield',
                                              'data-date-after': '#id_date_from'}),
        }


class EventSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):

    custom_domain = forms.URLField(
        label=_('Custom domain'),
        help_text=_('Enter a custom domain, such as https://my.event.org'),
        required=False,
    )
    show_schedule = forms.BooleanField(
        label=_('Show schedule publicly'),
        help_text=_('Unset to hide your schedule, e.g. if you want to use the HTML export exclusively.'),
        required=False,
    )
    export_html_on_schedule_release = forms.BooleanField(
        label=_('Generate HTML export on schedule release'),
        help_text=_('Set to make pretalx generate a static HTML version of your schedule, each time a new version is released.'),
        required=False,
    )
    display_header_pattern = forms.ChoiceField(
        label=_('Frontpage header pattern'),
        help_text=_('Choose how the frontpage header banner will be styled. Pattern source: <a href="http://www.heropatterns.com/">heropatterns.com</a>, CC BY 4.0.'),
        choices=(
            ('', _('Plain')),
            ('pcb', _('Circuits')),
            ('bubbles', _('Circles')),
            ('signal', _('Signal')),
            ('topo', _('Topography')),
            ('graph', _('Graph Paper')),
        ),
        required=False,
        widget=HeaderSelect,
    )


class MailSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    mail_from = forms.EmailField(
        label=_("Sender address"),
        help_text=_("Sender address for outgoing emails"))
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
