import logging
import os
from decimal import Decimal
from urllib.parse import urlparse

from django import forms
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from django_scopes import scope

from eventyay.timezones import common_timezones

from eventyay.base.forms import I18nModelForm, SettingsForm
from eventyay.base.meetup import (
    PRIVACY_CHOICES,
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    add_video_field_errors,
    apply_video_configuration,
    build_video_form_fields,
    get_rsvp_product_and_quota,
    get_video_config_initial,
    is_meetup_event,
    set_meetup_privacy,
)
from eventyay.base.models import Event
from eventyay.base.settings import validate_event_settings
from eventyay.common.language import get_language_choices_native_with_ui_name
from eventyay.common.urls import get_file_url_path, is_http_url
from eventyay.multidomain.urlreverse import build_absolute_uri
from eventyay.control.forms import MultipleLanguagesWidget, SlugWidget, SplitDateTimeField, SplitDateTimePickerWidget
from eventyay.control.forms.global_settings import StripeKeyValidator
from eventyay.helpers.image_optimize import optimize_uploaded_image
from eventyay.multidomain.models import KnownDomain

logger = logging.getLogger(__name__)


class EventCommonSettingsForm(SettingsForm):
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_('Event timezone'),
    )


    auto_fields = [
        'locales',
        'locale',
        'region',
        'contact_form_enabled',
        'contact_mail',
        'logo_image',
        'logo_image_large',
        'event_logo_image',
        'event_preview_image',
        'logo_show_title',
        'og_image',
        'primary_color',
        'header_background_color',
        'header_text_color',
        'navigation_text_color',
        'menu_text_scroll_over_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'video_navigation_background_color',
        'video_sidebar_text_color',
        'video_sidebar_hover_color',
        'theme_round_borders',
        'primary_font',
        'frontpage_text',
        'menu_label_tickets',
        'menu_label_join_video',
        'meta_noindex',
        'show_date_to',
        'show_times',
    ]

    def clean(self):
        data = super().clean()
        if data.get('contact_form_enabled') and not data.get('contact_mail'):
            self.add_error(
                'contact_mail',
                _('Please provide an email address for the contact form.'),
            )
        settings_dict = self.get_initial_settings()
        settings_dict.update(data)
        validate_event_settings(self.event, settings_dict)

        if is_meetup_event(self.event):
            add_video_field_errors(self, data.get('video_type'), data.get('video_url'))
            fee = data.get('registration_fee')
            if fee and fee > Decimal('0.00'):
                pub_key = data.get('payment_stripe_publishable_key') or self.event.settings.get('payment_stripe_publishable_key')
                sec_key = data.get('payment_stripe_secret_key') or self.event.settings.get('payment_stripe_secret_key')
                country = data.get('payment_stripe_merchant_country') or self.event.settings.get('payment_stripe_merchant_country')
                if not pub_key:
                    self.add_error('payment_stripe_publishable_key', _('Please enter your Stripe publishable key for paid registration.'))
                if not sec_key:
                    self.add_error('payment_stripe_secret_key', _('Please enter your Stripe secret key for paid registration.'))
                if not country:
                    self.add_error('payment_stripe_merchant_country', _('Please select your Stripe merchant country.'))

        return data

    def save(self):
        for image_field in ('event_logo_image', 'logo_image', 'event_preview_image', 'og_image'):
            current_value = self.event.settings.get(image_field, as_type=str, default='') or ''
            new_value = self.cleaned_data.get(image_field)
            current_file = get_file_url_path(current_value)
            if isinstance(new_value, UploadedFile) and current_file:
                default_storage.delete(current_file)

                base_path, unused_ext = os.path.splitext(current_file)
                orig_ext = self.event.settings.get(f'{image_field}_original_ext', as_type=str)
                if orig_ext:
                    default_storage.delete(f'{base_path}_original.{orig_ext}')

            if isinstance(new_value, UploadedFile):
                try:
                    prefix = self.add_prefix(image_field)
                    crop_x = int(float(self.data.get(f'{prefix}_crop_x', '')))
                    crop_y = int(float(self.data.get(f'{prefix}_crop_y', '')))
                    crop_w = int(float(self.data.get(f'{prefix}_crop_w', '')))
                    crop_h = int(float(self.data.get(f'{prefix}_crop_h', '')))
                    if crop_w <= 0 or crop_h <= 0:
                        raise ValueError('Invalid crop dimensions')
                    crop_box = (crop_x, crop_y, crop_x + crop_w, crop_y + crop_h)
                    self.event.settings.set(f'{image_field}_crop_data', f'{crop_x},{crop_y},{crop_w},{crop_h}')
                except (ValueError, TypeError) as e:
                    logger.error(f'Crop failed for {image_field}. Data keys: {[k for k in self.data.keys() if "crop" in k]}. Error: {e}')
                    crop_box = None
                self.cleaned_data[image_field] = self._save_optimized(new_value, image_field, crop_box)

        if is_meetup_event(self.event):
            self.cleaned_data.pop('meta_noindex', None)
            if 'privacy_type' in self.cleaned_data:
                is_priv = self.cleaned_data['privacy_type'] == PRIVACY_PRIVATE
                set_meetup_privacy(self.event, is_private=is_priv)

            if 'video_type' in self.cleaned_data:
                apply_video_configuration(
                    self.event,
                    self.cleaned_data.get('video_type'),
                    self.cleaned_data.get('video_url', ''),
                )

            if 'registration_limit' in self.cleaned_data:
                reg_limit = self.cleaned_data.get('registration_limit')
                product, quota = get_rsvp_product_and_quota(self.event)
                if quota and quota.size != reg_limit:
                    with scope(organizer=self.event.organizer):
                        quota.size = reg_limit
                        quota.save(update_fields=['size'])

            if 'registration_fee' in self.cleaned_data:
                reg_fee = self.cleaned_data.get('registration_fee') or Decimal('0.00')
                product, quota = get_rsvp_product_and_quota(self.event)
                if product and product.default_price != reg_fee:
                    with scope(organizer=self.event.organizer):
                        product.default_price = reg_fee
                        product.save(update_fields=['default_price'])

                stripe_sec = self.cleaned_data.get('payment_stripe_secret_key') or self.event.settings.get('payment_stripe_secret_key')
                if reg_fee > Decimal('0.00') and stripe_sec:
                    self.cleaned_data['payment_stripe__enabled'] = True
                elif reg_fee == Decimal('0.00') and not self.cleaned_data.get('payment_stripe_publishable_key'):
                    self.cleaned_data['payment_stripe_secret_key'] = ''
                    self.cleaned_data['payment_stripe_publishable_key'] = ''
                    self.cleaned_data['payment_stripe_merchant_country'] = ''
                    self.cleaned_data['payment_stripe__enabled'] = False

            if 'payment_stripe_secret_key' in self.cleaned_data and not self.cleaned_data.get('payment_stripe_secret_key'):
                if self.cleaned_data.get('registration_fee', Decimal('0.00')) > Decimal('0.00') or self.cleaned_data.get('payment_stripe__enabled'):
                    self.cleaned_data['payment_stripe_secret_key'] = self.initial.get('payment_stripe_secret_key', '')

        return super().save()

    def _save_optimized(self, uploaded: UploadedFile, setting_key: str, crop_box: tuple[int, int, int, int] | None = None) -> str | UploadedFile:
        """
        Resize and re-encode *uploaded*, persist the original alongside it,
        and return the path to the optimized file so that the settings form
        stores the optimized variant.
        """
        try:
            result = optimize_uploaded_image(uploaded, setting_key, crop_box)
        except Exception:
            logger.exception(
                'Image optimization failed for %s; storing original unmodified',
                setting_key,
            )
            uploaded.seek(0)
            return uploaded

        clean_name, unused_ext = os.path.splitext(uploaded.name or setting_key)
        new_filename = self.get_new_filename(clean_name)
        base_path, unused_ext = os.path.splitext(new_filename)

        # Persist the optimized file.
        optimized_name = f'{base_path}.{result.optimized_ext}'
        try:
            optimized_path = default_storage.save(optimized_name, result.optimized)
            logger.info('Stored optimized image at %s', optimized_path)
        except OSError:
            logger.exception('Could not store optimized image for %s', setting_key)
            return uploaded

        # Persist the original file alongside it.
        original_name = f'{base_path}_original.{result.original_ext}'
        try:
            original_path = default_storage.save(original_name, result.original)
            logger.info('Stored original image at %s', original_path)
            # Store the original extension so PR2 can easily find it later
            self.event.settings.set(f'{setting_key}_original_ext', result.original_ext)
        except OSError:
            logger.exception('Could not store original image for %s', setting_key)

        # Return a string so Hierarkey stores this path directly instead of wrapping it again
        return f"file://{optimized_path}"

    def __init__(self, *args, **kwargs):
        self.event = kwargs['obj']
        super().__init__(*args, **kwargs)

        # Meetup video stream & RSVP support
        if is_meetup_event(self.event):
            privacy_initial = PRIVACY_PRIVATE if not self.event.is_public else PRIVACY_PUBLIC
            self.fields['privacy_type'] = forms.ChoiceField(
                label=_('Visibility'),
                choices=PRIVACY_CHOICES,
                initial=privacy_initial,
                widget=forms.Select(attrs={'class': 'form-control'}),
                required=True,
                help_text=_(
                    'Public meetups appear on your organizer profile and search. '
                    'Private meetups are unlisted from your profile and accessible only via direct link.'
                ),
            )
            self.initial['privacy_type'] = privacy_initial
            self.fields.update(build_video_form_fields())
            self.initial.update(get_video_config_initial(self.event))

            self.fields['registration_limit'] = forms.IntegerField(
                required=False,
                min_value=1,
                label=_('Registration limit'),
                help_text=_('Maximum number of attendees who can RSVP. Leave empty for unlimited registrations.'),
            )
            product, quota = get_rsvp_product_and_quota(self.event)
            if quota and quota.size is not None:
                self.initial['registration_limit'] = quota.size

            self.fields['registration_fee'] = forms.DecimalField(
                required=False,
                min_value=Decimal('0.00'),
                decimal_places=2,
                max_digits=10,
                label=_('Registration fee amount'),
                help_text=_('Fee charged to attendees when registering for this meetup (in {currency}). Set to 0.00 for free registration.').format(
                    currency=self.obj.currency
                ),
                widget=forms.NumberInput(attrs={'placeholder': _('0.00 ({currency})').format(currency=self.obj.currency), 'step': '0.01'}),
            )
            if product:
                self.initial['registration_fee'] = product.default_price or Decimal('0.00')

            self.fields['payment_stripe__enabled'] = forms.BooleanField(
                label=_('Enable Stripe payment method'),
                required=False,
            )
            self.fields['payment_stripe_publishable_key'] = forms.CharField(
                label=_('Publishable key'),
                required=False,
                validators=(StripeKeyValidator(['pk_live_', 'pk_test_']),),
                widget=forms.TextInput(attrs={'placeholder': _('Publishable key')}),
            )
            self.fields['payment_stripe_secret_key'] = forms.CharField(
                label=_('Secret key'),
                required=False,
                validators=(StripeKeyValidator(['sk_live_', 'sk_test_', 'rk_live_', 'rk_test_']),),
                widget=forms.PasswordInput(render_value=True, attrs={'placeholder': _('Secret key'), 'autocomplete': 'new-password'}),
            )
            self.fields['payment_stripe_merchant_country'] = forms.ChoiceField(
                label=_('Merchant country'),
                required=False,
                choices=[('', _('Select country'))] + list(countries),
                help_text=_('The country in which your Stripe-account is registered in. Usually, this is your country of residence.'),
            )

            self.initial['payment_stripe__enabled'] = self.event.settings.get('payment_stripe__enabled', as_type=bool, default=False)
            self.initial['payment_stripe_publishable_key'] = self.event.settings.get('payment_stripe_publishable_key', default='')
            self.initial['payment_stripe_secret_key'] = self.event.settings.get('payment_stripe_secret_key', default='')
            self.initial['payment_stripe_merchant_country'] = self.event.settings.get('payment_stripe_merchant_country', default='')

        localized_language_choices = get_language_choices_native_with_ui_name()
        for fname in ('locales', 'content_locales'):
            if fname in self.fields:
                self.fields[fname].choices = localized_language_choices
        # Ensure the language selectors use the custom dropdown widget even if defaults are not picked up elsewhere,
        # while preserving any existing widget attributes (ids, data-*, classes).
        for fname in ('locales', 'content_locales'):
            if fname in self.fields:
                old_widget = self.fields[fname].widget
                self.fields[fname].widget = MultipleLanguagesWidget(
                    choices=self.fields[fname].choices, attrs=getattr(old_widget, 'attrs', None)
                )
        if self.event and 'content_locales' in self.fields:
            self.fields['content_locales'].initial = self.event.content_locales
        if is_meetup_event(self.event):
            self.fields.pop('meta_noindex', None)
            self.initial.pop('meta_noindex', None)
        elif 'meta_noindex' in self.fields:
            self.fields['meta_noindex'].label = _('Ask search engines not to index the event pages')

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs['data-eventyay-file-wrapper'] = 'disabled'
                field.widget.attrs['data-event-settings-image-tools'] = 'enabled'

        if not self.is_bound and self.event:
            contact_email = self.event.settings.contact_mail or self.event.email or ''
            if contact_email:
                if 'contact_form_enabled' in self.fields:
                    raw = self.event.settings.get('contact_form_enabled')
                    if raw in (None, '', False, 'False', 'false'):
                        self.fields['contact_form_enabled'].initial = True
                if 'contact_mail' in self.fields and not self.event.settings.contact_mail and self.event.email:
                    self.fields['contact_mail'].initial = self.event.email




class EventUpdateForm(I18nModelForm):
    def __init__(self, *args, **kwargs):
        self.change_slug = kwargs.pop('change_slug', False)
        self.domain_field_enabled = kwargs.pop('domain', False)

        kwargs.setdefault('initial', {})
        self.instance = kwargs['instance']
        if self.domain_field_enabled and self.instance:
            initial_domain = self.instance.domains.first()
            if initial_domain:
                kwargs['initial'].setdefault('domain', initial_domain.domainname)

        super().__init__(*args, **kwargs)
        if self.instance and self.instance.organizer:
            self.fields['slug'].widget.organizer = self.instance.organizer
            self.fields['slug'].widget.event = self.instance

        if not self.change_slug:
            self.fields['slug'].widget.attrs['readonly'] = 'readonly'
        self.fields['location'].widget.attrs['rows'] = '3'
        self.fields['location'].widget.attrs['placeholder'] = _('Sample Conference Center\nHeidelberg, Germany')
        self.fields['geo_lat'].widget.attrs['placeholder'] = _('Latitude, e.g. 40.7128')
        self.fields['geo_lon'].widget.attrs['placeholder'] = _('Longitude, e.g. -74.0060')

        if 'is_public' in self.fields:
            if is_meetup_event(self.instance):
                self.fields.pop('is_public', None)
            else:
                self.fields['is_public'].label = _('Show in search results and lists')
                self.fields['is_public'].help_text = _('If selected, this event will show up publicly on the list of events for your organizer account and in platform search results.')

        if self.domain_field_enabled:
            self.fields['domain'] = forms.CharField(
                max_length=255,
                label=_('Custom domain'),
                required=False,
                help_text=_('You need to configure the custom domain in the webserver beforehand.'),
            )

    def clean_domain(self):
        if not self.domain_field_enabled:
            return None
        d = self.cleaned_data.get('domain')
        if d:
            if d == urlparse(django_settings.SITE_URL).hostname:
                raise ValidationError(_('You cannot choose the base domain of this installation.'))
            if KnownDomain.objects.filter(domainname=d).exclude(event=self.instance.pk).exists():
                raise ValidationError(_('This domain is already in use for a different event or organizer.'))
        return d

    def save(self, commit=True):
        instance = super().save(commit)
        if self.domain_field_enabled and 'domain' in self.cleaned_data:
            current_domain = instance.domains.first()
            domain_value = self.cleaned_data['domain']
            if domain_value:
                if current_domain and current_domain.domainname != domain_value:
                    current_domain.delete()
                    KnownDomain.objects.create(
                        organizer=instance.organizer,
                        event=instance,
                        domainname=domain_value,
                    )
                elif not current_domain:
                    KnownDomain.objects.create(
                        organizer=instance.organizer,
                        event=instance,
                        domainname=domain_value,
                    )
            elif current_domain:
                current_domain.delete()
            instance.cache.clear()
        return instance

    def clean_slug(self):
        if self.change_slug:
            return self.cleaned_data['slug']
        return self.instance.slug

    class Meta:
        model = Event
        fields = [
            'name',
            'slug',
            'date_from',
            'date_to',
            'date_admission',
            'is_public',
            'location',
            'geo_lat',
            'geo_lon',
        ]
        field_classes = {
            'date_from': SplitDateTimeField,
            'date_to': SplitDateTimeField,
            'date_admission': SplitDateTimeField,
        }
        widgets = {
            'slug': SlugWidget(attrs={'data-slug-source': 'name'}),
            'date_from': SplitDateTimePickerWidget(),
            'date_to': SplitDateTimePickerWidget(attrs={'data-date-after': '#id_date_from_0'}),
            'date_admission': SplitDateTimePickerWidget(attrs={'data-date-default': '#id_date_from_0'}),
        }


class EventCloneForm(I18nModelForm):
    locales = forms.MultipleChoiceField(
        choices=django_settings.LANGUAGES,
        label=_('Event languages'),
        widget=MultipleLanguagesWidget,
        help_text=_(
            "Users will be able to use eventyay in these languages, and you will be able to provide all texts in "
            "these languages. If you don't provide a text in the language a user selects, it will be shown in your "
            "event's default language instead."
        ),
    )
    clone_common_data = forms.BooleanField(
        label=_('Common event Configuration'),
        help_text=_('Includes general settings, design elements, and email configurations.'),
        required=False,
        initial=True,
    )
    clone_settings = forms.BooleanField(
        label=_('General settings'),
        help_text=_('Location, currency, plugins, header/footer links.'),
        required=False,
        initial=True,
    )
    clone_design_texts = forms.BooleanField(
        label=_('Design and texts'),
        help_text=_('Colors, logo, custom CSS.'),
        required=False,
        initial=True,
    )
    clone_email_settings = forms.BooleanField(
        label=_('Email settings'),
        help_text=_('Email templates and SMTP configuration.'),
        required=False,
        initial=True,
    )

    clone_ticketing_data = forms.BooleanField(
        label=_('Ticketing Configuration'),
        help_text=_('Includes products, quotas, attendee questions, and check-in lists.'),
        required=False,
        initial=True,
    )
    clone_products = forms.BooleanField(
        label=_('Products & Quotas'),
        help_text=_('Ticket products, categories, quotas, tax rules, add-ons.'),
        required=False,
        initial=True,
    )
    clone_questions = forms.BooleanField(
        label=_('Questions'),
        help_text=_('Order and attendee questions.'),
        required=False,
        initial=True,
    )
    clone_checkin_lists = forms.BooleanField(
        label=_('Check-in lists'),
        help_text=_('Check-in lists configuration.'),
        required=False,
        initial=True,
    )
    clone_payment_settings = forms.BooleanField(
        label=_('Payment settings'),
        help_text=_('Payment providers and invoicing.'),
        required=False,
        initial=True,
    )

    clone_talk_data = forms.BooleanField(
        label=_('Talk Configuration'),
        help_text=_('Includes call for speakers, session tracks, and review settings.'),
        required=False,
        initial=True,
    )
    clone_cfp = forms.BooleanField(
        label=_('Call for speakers'),
        help_text=_('Call for speakers configuration and basic text.'),
        required=False,
        initial=True,
    )
    clone_session_types_tracks = forms.BooleanField(
        label=_('Session types & tracks'),
        help_text=_('Session types and tracks.'),
        required=False,
        initial=True,
    )
    clone_review_settings = forms.BooleanField(
        label=_('Review settings'),
        help_text=_('Review phases and review scoring categories.'),
        required=False,
        initial=True,
    )

    class Meta:
        model = Event
        fields = [
            'locales',
            'name',
            'slug',
            'date_from',
            'date_to',
            'timezone',
            'locale',
        ]
        field_classes = {
            'date_from': SplitDateTimeField,
            'date_to': SplitDateTimeField,
        }
        widgets = {
            'slug': SlugWidget(attrs={'data-slug-source': 'name'}),
            'date_from': SplitDateTimePickerWidget(),
            'date_to': SplitDateTimePickerWidget(attrs={'data-date-after': '#id_date_from_0'}),
        }

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.pop('organizer', None)
        self.locales = kwargs.get('locales')
        if self.locales is None and kwargs.get('initial'):
            self.locales = kwargs['initial'].get('locales')
        if not self.locales:
            self.locales = ['en']
        kwargs['locales'] = self.locales
        super().__init__(*args, **kwargs)
        if self.organizer:
            self.fields['slug'].widget.organizer = self.organizer
            self.fields['slug'].widget.prefix = build_absolute_uri(self.organizer, 'presale:organizer.index')
        self.fields['slug'].widget.attrs.setdefault('class', 'form-control')
        self.fields['timezone'].choices = ((a, a) for a in common_timezones)

        locale_choices = get_language_choices_native_with_ui_name()
        self.fields['locale'].choices = [(code, label) for code, label in locale_choices if code in self.locales]

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if Event.objects.filter(slug=slug, organizer=self.organizer).exists():
            raise forms.ValidationError(
                _('You already have an event with this short name. Please choose another one.')
            )
        return slug
