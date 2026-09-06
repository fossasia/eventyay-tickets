import logging
import os
from collections import OrderedDict
from typing import List, Union

from django import forms
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SECRET_REDACTED, SecretKeySettingsField, SecretKeySettingsWidget, SettingsForm
from eventyay.base.settings import EVENT_SERIES_CREATION_ENABLED, MEETUP_CREATION_ENABLED, GlobalSettingsObject
from eventyay.base.signals import register_global_settings
from eventyay.common.urls import get_file_url_path
from eventyay.consts import SizeKey
from eventyay.control.forms import ExtFileField
from eventyay.helpers.image_optimize import optimize_uploaded_image


logger = logging.getLogger(__name__)

class GlobalSettingsForm(SettingsForm):
    auto_fields = [
        'region',
        'mail_from',
        'seo_homepage_title',
        'seo_homepage_description',
        'seo_og_title',
        'seo_og_description',
        'seo_twitter_title',
        'seo_twitter_description',
        'seo_fallback_text',
    ]

    seo_social_image = ExtFileField(
        label=_('Social preview image'),
        ext_whitelist=('.png', '.jpg', '.gif', '.jpeg', '.webp'),
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE],
        required=False,
        help_text=_(
            'This image is used for Open Graph and Twitter cards. '
            'We recommend an image 1200 px wide and 630 px in height.'
        ),
    )

    def _setting_default(self):
        """
        Load default email setting form .cfg file if not set
        """
        global_settings = self.obj.settings
        if global_settings.get('billing_validation') is None:
            global_settings.set('billing_validation', True)
        if global_settings.get(EVENT_SERIES_CREATION_ENABLED) is None:
            global_settings.set(EVENT_SERIES_CREATION_ENABLED, True)
        if global_settings.get(MEETUP_CREATION_ENABLED) is None:
            global_settings.set(MEETUP_CREATION_ENABLED, False)
        if global_settings.get('smtp_port') is None or global_settings.get('smtp_port') == '':
            self.obj.settings.set('smtp_port', settings.EMAIL_PORT)
        if global_settings.get('smtp_host') is None or global_settings.get('smtp_host') == '':
            self.obj.settings.set('smtp_host', settings.EMAIL_HOST)
        if global_settings.get('smtp_username') is None or global_settings.get('smtp_username') == '':
            self.obj.settings.set('smtp_username', settings.EMAIL_HOST_USER)
        if global_settings.get('smtp_password') is None or global_settings.get('smtp_password') == '':
            self.obj.settings.set('smtp_password', settings.EMAIL_HOST_PASSWORD)
        if global_settings.get('smtp_use_tls') is None or global_settings.get('smtp_use_tls') == '':
            self.obj.settings.set('smtp_use_tls', settings.EMAIL_USE_TLS)
        if global_settings.get('smtp_use_ssl') is None or global_settings.get('smtp_use_ssl') == '':
            self.obj.settings.set('smtp_use_ssl', settings.EMAIL_USE_SSL)
        if global_settings.get('email_vendor') is None or global_settings.get('email_vendor') == '':
            self.obj.settings.set('email_vendor', 'smtp')

    def __init__(self, *args, **kwargs):
        self.obj = GlobalSettingsObject()
        self._setting_default()

        super().__init__(*args, obj=self.obj, **kwargs)

        smtp_select = [('sendgrid', _('SendGrid')), ('smtp', _('SMTP')), ('gmail_api', _('Gmail / Google Workspace API'))]

        self.fields = OrderedDict(
            list(self.fields.items())
            + [
                (
                    'allow_all_users_create_organizer',
                    forms.BooleanField(
                        label=_('All registered users can create organizers'),
                        help_text=_('If enabled, all registered users will be allowed to create organizers. System admins can always create organizers.'),
                        required=False,
                    ),
                ),
                (
                    'allow_payment_users_create_organizer',
                    forms.BooleanField(
                        label=_('All accounts with payment information can create organizers'),
                        help_text=_('If enabled, users with valid payment information on file will be allowed to create organizers. System admins can always create organizers.'),
                        required=False,
                    ),
                ),
                (
                    EVENT_SERIES_CREATION_ENABLED,
                    forms.BooleanField(
                        required=False,
                        label=_('Allow event series creation'),
                        help_text=_(
                            'When enabled, organizers can create event series or time slot bookings in addition to singular events. '
                            'Disable this to restrict event creation to singular events and non-event shops only.'
                        ),
                    ),
                ),
                (
                    MEETUP_CREATION_ENABLED,
                    forms.BooleanField(
                        required=False,
                        label=_('Allow meetup creation'),
                        help_text=_(
                            'When enabled, organizers can create simplified meetup events in addition to standard events. '
                            'Disable this to restrict event creation to standard events only.'
                        ),
                    ),
                ),

                (
                    'opencagedata_apikey',
                    SecretKeySettingsField(
                        required=False,
                        label=_('OpenCage API key for geocoding'),
                    ),
                ),
                (
                    'mapquest_apikey',
                    SecretKeySettingsField(
                        required=False,
                        label=_('MapQuest API key for geocoding'),
                    ),
                ),
                (
                    'nominatim_geocoding_enabled',
                    forms.BooleanField(
                        required=False,
                        label=_('Enable public Nominatim geocoding'),
                        help_text=_(
                            'Can be used alongside OpenCage or MapQuest as a fallback. In development, Nominatim '
                            'is used automatically when no API key is configured. Only enable in production if your '
                            'deployment can comply with the public Nominatim usage policy.'
                        ),
                    ),
                ),
                (
                    'leaflet_tiles',
                    forms.CharField(
                        required=False,
                        label=_('Leaflet tiles URL pattern'),
                        help_text=_('e.g. {sample}').format(sample='https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'),
                    ),
                ),
                (
                    'leaflet_tiles_attribution',
                    forms.CharField(
                        required=False,
                        label=_('Leaflet tiles attribution'),
                        help_text=_('e.g. {sample}').format(
                            sample='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        ),
                    ),
                ),
                (
                    'email_vendor',
                    forms.ChoiceField(
                        label=_('System Email'),
                        required=True,
                        widget=forms.RadioSelect,
                        choices=smtp_select,
                    ),
                ),
                (
                    'send_grid_api_key',
                    SecretKeySettingsField(
                        required=False,
                        label=_('Sendgrid token'),
                        widget=SecretKeySettingsWidget(attrs={
                            'placeholder': 'SG.xxxxxxxx',
                            'data-display-dependency': '#id_email_vendor_0',
                        }),
                    ),
                ),
                (
                    'gmail_client_id',
                    forms.CharField(
                        required=False,
                        label=_('Gmail OAuth client ID'),
                        help_text=_(
                            'Create an OAuth client in Google Cloud Console. The connect flow requests '
                            'Gmail send and user email scopes. Use the OAuth redirect URI shown below '
                            'as an authorized redirect URI.'
                        ),
                        widget=forms.TextInput(attrs={
                            'data-display-dependency': '#id_email_vendor_2',
                        }),
                    ),
                ),
                (
                    'gmail_client_secret',
                    SecretKeySettingsField(
                        required=False,
                        label=_('Gmail OAuth client secret'),
                        widget=SecretKeySettingsWidget(attrs={
                            'data-display-dependency': '#id_email_vendor_2',
                        }),
                    ),
                ),
                (
                    'smtp_host',
                    forms.CharField(
                        label=_('Hostname'),
                        required=False,
                        widget=forms.TextInput(attrs={
                            'placeholder': 'mail.example.org',
                            'data-display-dependency': '#id_email_vendor_1',
                        }),
                    ),
                ),
                (
                    'smtp_port',
                    forms.IntegerField(
                        label=_('Port'),
                        required=False,
                        widget=forms.TextInput(attrs={
                            'placeholder': 'e.g. 587, 465, 25, ...',
                            'data-display-dependency': '#id_email_vendor_1',
                        }),
                    ),
                ),
                (
                    'smtp_username',
                    forms.CharField(
                        label=_('Username'),
                        widget=forms.TextInput(attrs={
                            'placeholder': 'myuser@example.org',
                            'data-display-dependency': '#id_email_vendor_1',
                        }),
                        required=False,
                    ),
                ),
                (
                    'smtp_password',
                    SecretKeySettingsField(
                        label=_('Password'),
                        required=False,
                        widget=SecretKeySettingsWidget(
                            attrs={
                                'autocomplete': 'new-password',  # see https://bugs.chromium.org/p/chromium/issues/detail?id=370363#c7
                                'data-display-dependency': '#id_email_vendor_1',
                            }
                        ),
                    ),
                ),
                (
                    'smtp_use_tls',
                    forms.BooleanField(
                        label=_('Use STARTTLS'),
                        help_text=_('Commonly enabled on port 587.'),
                        required=False,
                        widget=forms.CheckboxInput(attrs={
                            'data-display-dependency': '#id_email_vendor_1',
                        }),
                    ),
                ),
                (
                    'smtp_use_ssl',
                    forms.BooleanField(
                        label=_('Use SSL'),
                        help_text=_('Commonly enabled on port 465.'),
                        required=False,
                        widget=forms.CheckboxInput(attrs={
                            'data-display-dependency': '#id_email_vendor_1',
                        }),
                    ),
                ),
                (
                    'update_check_perform',
                    forms.BooleanField(
                        required=False,
                        label=_('Perform update checks'),
                        help_text=_(
                            'During the update check, eventyay will report an anonymous, unique installation ID, '
                            'the current version of the system and your installed plugins and the number of active and '
                            'inactive events in your installation to servers operated by the eventyay developers. We '
                            'will only store anonymous data, never any IP addresses and we will not know who you are '
                            'or where to find your instance. You can disable this behavior here at any time.'
                        ),
                    ),
                ),
                (
                    'update_check_email',
                    forms.EmailField(
                        required=False,
                        label=_('E-mail notifications'),
                        help_text=_(
                            'We will notify you at this address if we detect that a new update is available. This '
                            'address will not be transmitted to eventyay.com, the emails will be sent by this server '
                            'locally.'
                        ),
                    ),
                ),
                (
                    'telemetry_enabled',
                    forms.BooleanField(
                        required=False,
                        label=_('Enable telemetry'),
                        help_text=_(
                            'Send anonymous usage statistics (bucketed counts, deployment info) to help track '
                            'version adoption and deployment patterns. No personal data is collected. '
                            'Data is sent approximately once per day.'
                        ),
                    ),
                ),
                (
                    'telemetry_endpoint',
                    forms.URLField(
                        required=False,
                        label=_('Telemetry endpoint'),
                        help_text=_('The URL where telemetry data will be sent (Google Apps Script URL).'),
                    ),
                ),
                (
                    'telemetry_api_key',
                    SecretKeySettingsField(
                        required=False,
                        label=_('Telemetry API key'),
                        help_text=_('API key for authenticating with the telemetry receiver.'),
                    ),
                ),
                (
                    'telemetry_contact_email',
                    forms.EmailField(
                        required=False,
                        label=_('Maintainer contact'),
                        help_text=_(
                            'Optional email address included in telemetry data to identify who maintains this instance. '
                            'Only visible to those with access to the telemetry data sheet.'
                        ),
                    ),
                ),
                # Etherpad collaborative notes
                (
                    'etherpad_enabled',
                    forms.BooleanField(
                        label=_('Enable Etherpad integration'),
                        help_text=_('Allow events to attach collaborative Etherpad notes to their sessions.'),
                        required=False,
                    ),
                ),
                (
                    'etherpad_base_url',
                    forms.URLField(
                        label=_('Default Etherpad instance URL'),
                        help_text=_('Base URL of the Etherpad instance, e.g. {sample}').format(sample='https://pad.example.org'),
                        required=False,
                    ),
                ),
                (
                    'etherpad_api_key',
                    SecretKeySettingsField(
                        label=_('Etherpad API key'),
                        help_text=_(
                            'API key of the Etherpad instance (found in APIKEY.txt). Required only for automatic pad '
                            'creation; without it, pad links are generated as plain URLs that Etherpad creates on first visit.'
                        ),
                        required=False,
                    ),
                ),
                (
                    'etherpad_pad_name_pattern',
                    forms.CharField(
                        label=_('Pad name pattern'),
                        help_text=_(
                            'Pattern used to generate pad names. Available placeholders: {placeholders}.'
                        ).format(placeholders='{event}, {submission}, {token}'),
                        required=False,
                    ),
                ),
            ]
        )
        responses = register_global_settings.send(self)
        for r, response in sorted(responses, key=lambda r: str(r[0])):
            for key, value in response.items():
                # Payment settings belong to Ticketing, not GlobalSettingsForm
                if not key.startswith('payment_'):
                    self.fields[key] = value

        # VoxBento
        if 'voxbento_base_url' not in self.fields:
            self.fields['voxbento_base_url'] = forms.URLField(
                label=_('VoxBento Base URL'),
                required=False,
                help_text=_('Base URL of the VoxBento interpretation server (e.g. https://interpretation.eventyay.com).'),
            )
        if 'voxbento_client_id' not in self.fields:
            self.fields['voxbento_client_id'] = forms.CharField(
                label=_('VoxBento Client ID'),
                required=False,
                help_text=_('Client ID for authenticating with VoxBento API.'),
            )
        if 'voxbento_client_secret' not in self.fields:
            self.fields['voxbento_client_secret'] = SecretKeySettingsField(
                label=_('VoxBento Client Secret'),
                required=False,
                help_text=_('Client Secret for authenticating with VoxBento API.'),
            )

        # HubSpot
        if 'hubspot_client_id' not in self.fields:
            self.fields['hubspot_client_id'] = forms.CharField(
                label=_('HubSpot Client ID'),
                required=False,
            )
        if 'hubspot_client_secret' not in self.fields:
            self.fields['hubspot_client_secret'] = SecretKeySettingsField(
                label=_('HubSpot Client Secret'),
                required=False,
            )
        if 'hubspot_property_sync_ttl_minutes' not in self.fields:
            self.fields['hubspot_property_sync_ttl_minutes'] = forms.IntegerField(
                label=_('HubSpot Property Sync TTL (minutes)'),
                required=False,
                min_value=0,
                initial=60,
            )

        self.field_groups = [
            ('meta-data', _('Meta data'), [
                'seo_homepage_title',
                'seo_homepage_description',
                'seo_og_title',
                'seo_og_description',
                'seo_twitter_title',
                'seo_twitter_description',
                'seo_fallback_text',
                'seo_social_image',
            ]),
            ('event-creation', _('Event Creation'), [
                EVENT_SERIES_CREATION_ENABLED,
                MEETUP_CREATION_ENABLED,
            ]),
            ('organizers', _('Organizers'), [
                'allow_all_users_create_organizer',
                'allow_payment_users_create_organizer',
            ]),
            ('localization', _('Localization'), [
                'region',
            ]),
            ('email', _('Email'), [
                'mail_from', 'email_vendor', 'send_grid_api_key',
                'gmail_client_id', 'gmail_client_secret',
                'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
                'smtp_use_tls', 'smtp_use_ssl',
            ]),
            ('update-check', _('Update check'), [
                'update_check_perform',
                'update_check_email',
                'telemetry_enabled',
                'telemetry_endpoint',
                'telemetry_api_key',
                'telemetry_contact_email',
            ]),
            ('maps', _('Maps'), [
                'opencagedata_apikey', 'mapquest_apikey', 'nominatim_geocoding_enabled', 'leaflet_tiles', 'leaflet_tiles_attribution',
            ]),
            ('etherpad', _('Etherpad'), [
                'etherpad_enabled',
                'etherpad_base_url',
                'etherpad_api_key',
                'etherpad_pad_name_pattern',
            ]),
            ('voxbento', _('VoxBento'), [
                'voxbento_base_url',
                'voxbento_client_id',
                'voxbento_client_secret',
            ]),
            ('hubspot', _('HubSpot'), [
                'hubspot_client_id',
                'hubspot_client_secret',
                'hubspot_property_sync_ttl_minutes',
            ]),
        ]

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs['data-eventyay-file-wrapper'] = 'disabled'
                field.widget.attrs['data-event-settings-image-tools'] = 'enabled'

    def clean_voxbento_base_url(self):
        url = (self.cleaned_data.get('voxbento_base_url') or '').strip()
        if url:
            if url.endswith('/'):
                url = url[:-1]
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url
        return url

    def clean_etherpad_pad_name_pattern(self):
        pattern = (self.cleaned_data.get('etherpad_pad_name_pattern') or '').strip()
        if pattern and '{submission}' not in pattern and '{token}' not in pattern:
            raise forms.ValidationError(
                _('The pattern must contain {submission} or {token} so each session gets a unique pad.')
            )
        return pattern

    def clean(self):
        data = super().clean()

        # Validate SendGrid token is provided when SendGrid is selected
        if data.get('email_vendor') == 'sendgrid':
            if not data.get('send_grid_api_key'):
                raise forms.ValidationError({'send_grid_api_key': _('This field is required when using SendGrid as email vendor.')})
        if data.get('email_vendor') == 'gmail_api':
            if not (data.get('gmail_client_id') or '').strip():
                raise forms.ValidationError({'gmail_client_id': _('This field is required when using Gmail as email vendor.')})
            secret = data.get('gmail_client_secret')
            has_secret = (
                secret == SECRET_REDACTED
                or bool((secret or '').strip())
                or self.obj.settings.get('gmail_client_secret')
            )
            if not has_secret:
                raise forms.ValidationError({'gmail_client_secret': _('This field is required when using Gmail as email vendor.')})

        return data

    def save(self):
        image_field = 'seo_social_image'
        current_value = self.obj.settings.get(image_field, as_type=str, default='') or ''
        new_value = self.cleaned_data.get(image_field)

        if isinstance(new_value, UploadedFile):

            clean_name, ext = os.path.splitext(new_value.name or image_field)
            new_filename = self.get_new_filename(clean_name)
            base_path, _ = os.path.splitext(new_filename)
            optimized_name = f'{base_path}{ext}'
            try:
                optimized_path = default_storage.save(optimized_name, new_value)
                self.cleaned_data[image_field] = f"file://{optimized_path}"
                current_file = get_file_url_path(current_value)
                if current_file:
                    default_storage.delete(current_file)
            except OSError:
                logger.exception('Could not store original image for %s', image_field)
                self.cleaned_data[image_field] = current_value

        return super().save()


class GlobalTicketingSettingsForm(SettingsForm):
    def _setting_default(self):
        global_settings = self.obj.settings
        if global_settings.get('reservation_time') is None or global_settings.get('reservation_time') == '':
            global_settings.set('reservation_time', 30)
        if global_settings.get('max_products_per_order') is None or global_settings.get('max_products_per_order') == '':
            global_settings.set('max_products_per_order', 0)

    def __init__(self, *args, **kwargs):
        self.obj = GlobalSettingsObject()
        self._setting_default()
        super().__init__(*args, obj=self.obj, **kwargs)

        self.fields = OrderedDict(
            list(self.fields.items())
            + [
                # Stripe for ticket payments
                (
                    'payment_stripe_connect_client_id',
                    forms.CharField(
                        label=_('Client ID'),
                        required=False,
                        help_text=_('Stripe Connect client ID for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_publishable_key',
                    forms.CharField(
                        label=_('Publishable key (Live)'),
                        required=False,
                        validators=(StripeKeyValidator('pk_live_'),),
                        help_text=_('Live publishable key for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key (Live)'),
                        required=False,
                        validators=(StripeKeyValidator(['sk_live_', 'rk_live_']),),
                        help_text=_('Live secret key for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_test_publishable_key',
                    forms.CharField(
                        label=_('Publishable key (Test)'),
                        required=False,
                        validators=(StripeKeyValidator('pk_test_'),),
                        help_text=_('Test publishable key for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_test_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key (Test)'),
                        required=False,
                        validators=(StripeKeyValidator(['sk_test_', 'rk_test_']),),
                        help_text=_('Test secret key for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_app_fee_percent',
                    forms.DecimalField(
                        label=_('App fee percentage'),
                        required=False,
                        decimal_places=2,
                        max_digits=10,
                        help_text=_('Percentage fee charged on ticket payments.'),
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    'payment_stripe_connect_app_fee_min',
                    forms.DecimalField(
                        label=_('App fee minimum'),
                        required=False,
                        decimal_places=2,
                        max_digits=10,
                        help_text=_('Minimum fee amount charged on ticket payments.'),
                        validators=[MinValueValidator(0)],
                    ),
                ),
                (
                    'payment_stripe_connect_app_fee_max',
                    forms.DecimalField(
                        label=_('App fee maximum'),
                        required=False,
                        decimal_places=2,
                        max_digits=10,
                        help_text=_('Maximum fee amount charged on ticket payments.'),
                        validators=[MinValueValidator(0)],
                    ),
                ),
                # PayPal
                (
                    'payment_paypal_connect_client_id',
                    forms.CharField(
                        label=_('Client ID'),
                        required=False,
                        help_text=_('PayPal Connect client ID for payment processing.'),
                    ),
                ),
                (
                    'payment_paypal_connect_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key'),
                        required=False,
                        help_text=_('PayPal Connect secret key for payment processing.'),
                    ),
                ),
                (
                    'payment_paypal_connect_endpoint',
                    forms.CharField(
                        label=_('API Endpoint'),
                        required=False,
                        help_text=_('PayPal API endpoint (e.g., https://api.paypal.com or https://api.sandbox.paypal.com).'),
                    ),
                ),
                # Cart
                (
                    'reservation_time',
                    forms.IntegerField(
                        label=_('Reservation period'),
                        help_text=_("The number of minutes the items in a user's cart are reserved for this user."),
                        min_value=0,
                        required=True,
                    ),
                ),
                (
                    'max_products_per_order',
                    forms.IntegerField(
                        label=_('Maximum number of items per order'),
                        help_text=_('Add-on products will be excluded from the count. Set to 0 for unlimited.'),
                        min_value=0,
                        required=True,
                    ),
                ),
            ]
        )

        responses = register_global_settings.send(self)
        payment_gateway_fields = [
            # Stripe for Ticket Payments
            'payment_stripe_connect_client_id',
            'payment_stripe_connect_publishable_key',
            'payment_stripe_connect_secret_key',
            'payment_stripe_connect_test_publishable_key',
            'payment_stripe_connect_test_secret_key',
            'payment_stripe_connect_app_fee_percent',
            'payment_stripe_connect_app_fee_min',
            'payment_stripe_connect_app_fee_max',

            # PayPal
            'payment_paypal_connect_client_id',
            'payment_paypal_connect_secret_key',
            'payment_paypal_connect_endpoint',
        ]
        for r, response in sorted(responses, key=lambda r: str(r[0])):
            for key, value in response.items():
                if key.startswith('payment_'):
                    if key not in self.fields:
                        self.fields[key] = value
                    if key not in payment_gateway_fields:
                        payment_gateway_fields.append(key)

        self.field_groups = [
            ('payment-gateways', _('Payment Gateways'), payment_gateway_fields),
            ('cart', _('Cart'), [
                'reservation_time',
                'max_products_per_order',
            ]),
        ]


class SSOConfigForm(SettingsForm):
    redirect_url = forms.URLField(
        required=True,
        label=_('Redirect URL'),
        help_text=_('e.g. {sample}').format(sample='https://app-test.eventyay.com/talk/oauth2/callback/'),
    )

    def __init__(self, *args, **kwargs):
        self.obj = GlobalSettingsObject()
        super().__init__(*args, obj=self.obj, **kwargs)


class StripeKeyValidator:
    """
    Validates that a given Stripe key starts with the expected prefix(es).

    This validator ensures that Stripe API keys conform to the expected format
    by checking their prefixes. It supports both single prefix validation and
    multiple prefix validation.
    """

    def __init__(self, prefix: Union[str, List[str]]) -> None:
        if not prefix:
            raise ValueError('Prefix cannot be empty')

        if isinstance(prefix, list):
            if not all(isinstance(p, str) and p for p in prefix):
                raise ValueError('All prefixes must be non-empty strings')
            self._prefixes = prefix
        elif isinstance(prefix, str):
            if not prefix.strip():
                raise ValueError('Prefix cannot be whitespace')
            self._prefixes = [prefix]

    def __call__(self, value: str) -> None:
        if not value:
            raise forms.ValidationError(_('The Stripe key cannot be empty.'), code='invalid-stripe-key')

        if not any(value.startswith(p) for p in self._prefixes):
            if len(self._prefixes) == 1:
                message = _('The provided key does not look valid. It should start with "%(prefix)s".')
                params = {'value': value, 'prefix': self._prefixes[0]}
            else:
                message = _('The provided key does not look valid. It should start with one of: %(prefixes)s')
                params = {
                    'value': value,
                    'prefixes': ', '.join(f'"{p}"' for p in self._prefixes),
                }

            raise forms.ValidationError(message, code='invalid-stripe-key', params=params)


class GlobalBusinessSettingsForm(SettingsForm):
    def __init__(self, *args, **kwargs):
        self.obj = GlobalSettingsObject()
        super().__init__(*args, obj=self.obj, **kwargs)

        self.fields.update(
            OrderedDict([
                # Stripe for Organizer Billing
                (
                    'payment_stripe_publishable_key',
                    forms.CharField(
                        label=_('Publishable key (Live)'),
                        required=False,
                        validators=(StripeKeyValidator('pk_live_'),),
                        help_text=_('Live publishable key for organizer billing and platform fees.'),
                    ),
                ),
                (
                    'payment_stripe_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key (Live)'),
                        required=False,
                        validators=(StripeKeyValidator(['sk_live_', 'rk_live_']),),
                        help_text=_('Live secret key for organizer billing and platform fees.'),
                    ),
                ),
                (
                    'payment_stripe_test_publishable_key',
                    forms.CharField(
                        label=_('Publishable key (Test)'),
                        required=False,
                        validators=(StripeKeyValidator('pk_test_'),),
                        help_text=_('Test publishable key for organizer billing and platform fees.'),
                    ),
                ),
                (
                    'payment_stripe_test_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key (Test)'),
                        required=False,
                        validators=(StripeKeyValidator(['sk_test_', 'rk_test_']),),
                        help_text=_('Test secret key for organizer billing and platform fees.'),
                    ),
                ),
                (
                    'stripe_webhook_secret_key',
                    SecretKeySettingsField(
                        label=_('Webhook secret key'),
                        required=False,
                        help_text=_('Configure this endpoint in your Stripe dashboard to receive billing events.'),
                    ),
                ),
                (
                    'ticket_fee_percentage',
                    forms.DecimalField(
                        label=_('Ticket fee percentage'),
                        required=False,
                        decimal_places=2,
                        max_digits=10,
                        help_text=_('A percentage fee will be charged for each ticket sold.'),
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    'billing_validation',
                    forms.BooleanField(
                        required=False,
                        label=_('Billing validation'),
                        help_text=_(
                            'Billing validation lets you require organizers to set up a billing method before they can create events. '
                            'When this option is enabled, no new event can be created until a valid billing method has been added.'
                        ),
                    ),
                ),
            ])
        )

        if 'billing_validation' not in self.initial or self.initial['billing_validation'] is None:
            self.initial['billing_validation'] = self.obj.settings.get('billing_validation', as_type=bool, default=True)

        self.field_groups = [
            ('organizer_billing', _('Organizer Billing'), [
                'payment_stripe_publishable_key',
                'payment_stripe_secret_key',
                'payment_stripe_test_publishable_key',
                'payment_stripe_test_secret_key',
                'stripe_webhook_secret_key',
            ]),
            ('ticket_fee', _('Ticket Fee'), [
                'ticket_fee_percentage',
            ]),
            ('billing_validation', _('Billing Validation'), [
                'billing_validation',
            ]),
        ]
