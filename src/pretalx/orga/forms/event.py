import socket
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.fields import I18nFormField, I18nTextarea
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.css import validate_css
from pretalx.common.forms.fields import IMAGE_EXTENSIONS, ExtensionFileField
from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.phrases import phrases
from pretalx.event.models.event import Event, Event_SettingsStore
from pretalx.orga.forms.widgets import HeaderSelect, MultipleLanguagesWidget


class EventForm(ReadOnlyFlag, I18nModelForm):
    locales = forms.MultipleChoiceField(
        label=_('Active languages'),
        choices=settings.LANGUAGES,
        widget=MultipleLanguagesWidget,
    )
    logo = ExtensionFileField(
        required=False,
        extension_whitelist=IMAGE_EXTENSIONS,
        label=_('Logo'),
        help_text=_(
            'If you provide a logo image, we will by default not show your event\'s name and date in the page header. '
            'We will show your logo in its full size if possible, scaled down to the full header width otherwise.'
        ),
    )

    def __init__(self, *args, **kwargs):
        self.is_administrator = kwargs.pop('is_administrator', False)
        super().__init__(*args, **kwargs)
        self.initial['locales'] = self.instance.locale_array.split(',')
        year = str(now().year)
        self.fields['name'].widget.attrs['placeholder'] = (
            _('The name of your conference, e.g. My Conference') + ' ' + year
        )
        self.fields['slug'].widget.attrs['placeholder'] = (
            _('A short version of your conference name, e.g. mycon') + year[2:]
        )
        self.fields['primary_color'].widget.attrs['placeholder'] = _(
            'A color hex value, e.g. #ab01de'
        )
        self.fields['primary_color'].widget.attrs['class'] = 'colorpickerfield'
        self.fields['slug'].disabled = True

    def clean_custom_css(self):

        if self.cleaned_data.get('custom_css') or self.files.get('custom_css'):
            css = self.cleaned_data['custom_css'] or self.files['custom_css']
            if self.is_administrator:
                return css
            try:
                validate_css(css.read())
                return css
            except IsADirectoryError:
                self.instance.custom_css = None
                self.instance.save(update_fields=['custom_css'])
        else:
            self.instance.custom_css = None
            self.instance.save(update_fields=['custom_css'])
        return None

    def clean(self):
        data = super().clean()
        if data.get('locale') not in data.get('locales', []):
            raise forms.ValidationError(
                _('Your default language needs to be one of your active languages.')
            )
        if not data.get('email'):
            raise forms.ValidationError(
                _(
                    'Please provide a contact address – your speakers and participants should be able to reach you easily.'
                )
            )
        return data

    def save(self, *args, **kwargs):
        self.instance.locale_array = ','.join(self.cleaned_data['locales'])
        return super().save(*args, **kwargs)

    class Meta:
        model = Event
        fields = [
            'name',
            'slug',
            'date_from',
            'date_to',
            'timezone',
            'email',
            'locale',
            'primary_color',
            'custom_css',
            'logo',
            'landing_page_text',
        ]
        widgets = {
            'date_from': forms.DateInput(attrs={'class': 'datepickerfield'}),
            'date_to': forms.DateInput(
                attrs={'class': 'datepickerfield', 'data-date-after': '#id_date_from'}
            ),
        }


class EventSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):

    custom_domain = forms.URLField(
        label=_('Custom domain'),
        help_text=_('Enter a custom domain, such as https://my.event.example.org'),
        required=False,
    )
    show_on_dashboard = forms.BooleanField(
        label=_('Show on dashboard'),
        help_text=_(
            'Set to show this event on this website\'s public dashboard. Will only show if the event is public.'
        ),
        required=False,
    )
    show_schedule = forms.BooleanField(
        label=_('Show schedule publicly'),
        help_text=_(
            'Unset to hide your schedule, e.g. if you want to use the HTML export exclusively.'
        ),
        required=False,
    )
    show_sneak_peek = forms.BooleanField(
        label=_('Show a sneak peek before schedule release'),
        help_text=_(
            'Set to publicly display a list of talks, which have the "is featured" flag enabled.'
        ),
        required=False,
    )
    export_html_on_schedule_release = forms.BooleanField(
        label=_('Generate HTML export on schedule release'),
        help_text=_(
            'The static HTML export will be provided as a .zip archive on the schedule export page.'
        ),
        required=False,
    )
    html_export_url = forms.URLField(
        label=_('HTML Export URL'),
        help_text=_(
            'If you publish your schedule via the HTML export, you will want the correct absolute URL to be set in various places. '
            'Please only set this value once you have published your schedule. Should end with a slash.'
        ),
        required=False,
    )
    display_header_pattern = forms.ChoiceField(
        label=_('Frontpage header pattern'),
        help_text=_(
            'Choose how the frontpage header banner will be styled. Pattern source: <a href="http://www.heropatterns.com/">heropatterns.com</a>, CC BY 4.0.'
        ),
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
    meta_noindex = forms.BooleanField(
        label=_('Ask search engines not to index the event pages'), required=False
    )

    def clean_custom_domain(self):
        data = self.cleaned_data['custom_domain']
        if not data:
            return data
        if data == urlparse(settings.SITE_URL).hostname or data == settings.SITE_URL:
            raise ValidationError(
                _('You cannot choose the base domain of this installation.')
            )
        known_domains = [
            domain
            for domain in set(
                Event_SettingsStore.objects.filter(key='custom_domain').values_list(
                    'value', flat=True
                )
            )
            if domain
        ]
        parsed_domains = [urlparse(domain).hostname for domain in known_domains]
        if data in known_domains or data in parsed_domains:
            raise ValidationError(
                _('This domain is already in use for a different event.')
            )
        if not data.startswith('https://'):
            if data.startswith('http://'):
                data.lstrip('http://')
            data = 'https://' + data
        data = data.rstrip('/')
        try:
            socket.gethostbyname(data.lstrip('https://'))
        except OSError as e:
            raise forms.ValidationError(_('The domain "{domain}" does not have a name server entry at this time.').format(domain=data))
        return data


class MailSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    mail_from = forms.EmailField(
        label=_('Sender address'),
        help_text=_('Sender address for outgoing emails.'),
        required=False,
    )
    mail_subject_prefix = forms.CharField(
        label=_('Mail subject prefix'),
        help_text=_(
            'The prefix will be prepended to outgoing mail subjects in [brackets].'
        ),
        required=False,
    )
    mail_signature = forms.CharField(
        label=_('Mail signature'),
        help_text=_(
            'The signature will be added to outgoing mails, preceded by "-- ".'
        ),
        required=False,
        widget=forms.Textarea,
    )
    smtp_use_custom = forms.BooleanField(
        label=_('Use custom SMTP server'),
        help_text=_(
            'All mail related to your event will be sent over the SMTP server specified by you.'
        ),
        required=False,
    )
    smtp_host = forms.CharField(label=_("Hostname"), required=False)
    smtp_port = forms.IntegerField(label=_("Port"), required=False)
    smtp_username = forms.CharField(label=_("Username"), required=False)
    smtp_password = forms.CharField(
        label=_("Password"),
        required=False,
        widget=forms.PasswordInput(
            attrs={
                'autocomplete': 'new-password'  # see https://bugs.chromium.org/p/chromium/issues/detail?id=370363#c7
            }
        ),
    )
    smtp_use_tls = forms.BooleanField(
        label=_("Use STARTTLS"),
        help_text=_("Commonly enabled on port 587."),
        required=False,
    )
    smtp_use_ssl = forms.BooleanField(
        label=_("Use SSL"), help_text=_("Commonly enabled on port 465."), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        event = kwargs.get('obj')
        if event:
            self.fields['mail_from'].widget.attrs['placeholder'] = event.email
            self.fields['mail_from'].help_text += _(
                'Leave empty to use the default address: {}'
            ).format(event.email)

    def clean(self):
        data = self.cleaned_data
        if not data.get('smtp_password') and data.get('smtp_username'):
            # Leave password unchanged if the username is set and the password field is empty.
            # This makes it impossible to set an empty password as long as a username is set, but
            # Python's smtplib does not support password-less schemes anyway.
            data['smtp_password'] = self.initial.get('smtp_password')

        if data.get('smtp_use_tls') and data.get('smtp_use_ssl'):
            raise ValidationError(
                _(
                    'You can activate either SSL or STARTTLS security, but not both at the same time.'
                )
            )
        uses_encryption = data.get('smtp_use_tls') or data.get('smtp_use_ssl')
        localhost_names = [
            '127.0.0.1',
            '::1',
            '[::1]',
            'localhost',
            'localhost.localdomain',
        ]
        if not uses_encryption and not data.get('smtp_host') in localhost_names:
            raise ValidationError(
                _(
                    'You have to activate either SSL or STARTTLS security if you use a non-local mailserver due to data protection reasons. '
                    'Your administrator can add an instance-wide bypass. If you use this bypass, please also adjust your Privacy Policy.'
                )
            )


class ReviewSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    review_deadline = forms.DateTimeField(label=_('Review deadline'), required=False)
    review_hide_speaker_names = forms.BooleanField(
        label=_('Hide speaker names'),
        help_text=_(
            'Prevent reviewers from seeing speaker names. Please note that reviewers who also have organiser rights will still see speaker names.'
        ),
        required=False,
    )
    allow_override_votes = forms.BooleanField(
        label=_('Allow override votes'),
        help_text=_(
            'Review teams can be assigned a fixed amount of "override votes": Positive or negative vetos each reviewer can assign.'
        ),
        required=False,
    )
    review_score_mandatory = forms.BooleanField(
        label=_('Require a review score'), required=False
    )
    review_text_mandatory = forms.BooleanField(
        label=_('Require a review text'), required=False
    )
    review_help_text = I18nFormField(
        label=_('Help text for reviewers'),
        help_text=_(
            'This text will be shown at the top of every review, as long as reviews can be created or edited.'
        )
        + ' '
        + phrases.base.use_markdown,
        widget=I18nTextarea,
        required=False,
    )
    review_min_score = forms.IntegerField(
        label=_('Minimum score'), help_text=_('The minimum score reviewers can assign')
    )
    review_max_score = forms.IntegerField(
        label=_('Maximum score'), help_text=_('The maximum score reviewers can assign')
    )

    def __init__(self, obj, *args, **kwargs):
        super().__init__(*args, obj=obj, **kwargs)
        if getattr(obj, 'slug'):
            additional = _(
                'You can configure override votes <a href="{link}">in the team settings</a>.'
            ).format(link=obj.orga_urls.team_settings)
            self.fields['allow_override_votes'].help_text += f' {additional}'
        minimum = int(obj.settings.review_min_score)
        maximum = int(obj.settings.review_max_score)
        self.fields['review_deadline'].widget = forms.DateTimeInput(
            attrs={'class': 'datetimepickerfield'}
        )
        for number in range(abs(maximum - minimum + 1)):
            index = minimum + number
            self.fields[f'review_score_name_{index}'] = forms.CharField(
                label=_('Score label ({})').format(index),
                help_text=_(
                    'Human readable explanation of what a score of "{}" actually means, e.g. "great!".'
                ).format(index),
                required=False,
            )

    def clean(self):
        data = self.cleaned_data
        minimum = int(data.get('review_min_score'))
        maximum = int(data.get('review_max_score'))
        if minimum >= maximum:
            raise forms.ValidationError(
                _('Please assign a minimum score smaller than the maximum score!')
            )
        return data
