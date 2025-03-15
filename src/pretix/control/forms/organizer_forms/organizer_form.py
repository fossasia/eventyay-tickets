import pyvat
from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from pretix.base.forms import I18nModelForm
from pretix.base.models.organizer import Organizer, OrganizerBillingModel
from pretix.base.models.vouchers import InvoiceVoucher
from pretix.helpers.countries import CachedCountries, get_country_name
from pretix.helpers.stripe_utils import (
    create_stripe_customer,
    update_customer_info,
)


class OrganizerForm(I18nModelForm):
    error_messages = {
        'duplicate_slug': _(
            'This slug is already in use. Please choose a different one.'
        ),
    }

    class Meta:
        model = Organizer
        fields = ['name', 'slug']

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if Organizer.objects.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(
                self.error_messages['duplicate_slug'],
                code='duplicate_slug',
            )
        return slug


class BillingSettingsForm(forms.ModelForm):
    class Meta:
        model = OrganizerBillingModel
        fields = [
            'primary_contact_name',
            'primary_contact_email',
            'company_or_organization_name',
            'address_line_1',
            'address_line_2',
            'zip_code',
            'city',
            'country',
            'preferred_language',
            'tax_id',
            'invoice_voucher',
        ]

    primary_contact_name = forms.CharField(
        label=_('Primary Contact Name'),
        help_text=_(
            'Please provide your name or the name of the person responsible for this account in your organization.'
        ),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': ''}),
    )

    primary_contact_email = forms.EmailField(
        label=_('Primary Contact Email'),
        help_text=_(
            'We will use this email address for all communication related to your contract and billing, '
            'as well as for important updates about your account and our services.'
        ),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': ''}),
    )

    company_or_organization_name = forms.CharField(
        label=_('Company or Organization Name'),
        help_text=_('Enter your organization’s legal name.'),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': ''}),
    )

    address_line_1 = forms.CharField(
        label=_('Address Line 1'),
        help_text=_('Street address or P.O. box.'),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': ''}),
    )

    address_line_2 = forms.CharField(
        label=_('Address Line 2'),
        help_text=_('Apartment, suite, unit, etc. (optional).'),
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': ''}),
    )

    zip_code = forms.CharField(
        label=_('Zip Code'),
        help_text=_('Enter your postal code.'),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': ''}),
    )

    city = forms.CharField(
        label=_('City'),
        help_text=_('Enter your city.'),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': ''}),
    )

    country = forms.ChoiceField(
        label=_('Country'),
        help_text=_('Select your country.'),
        required=True,
        choices=CachedCountries(),
        initial='US',
    )

    preferred_language = forms.ChoiceField(
        label=_('Preferred Language for Correspondence'),
        help_text=_('Select your preferred language for all communication.'),
        required=True,
    )

    tax_id = forms.CharField(
        label=_('Tax ID (e.g., VAT, GST)'),
        help_text=_(
            'If you are located in the EU, please provide your VAT ID. '
            'Without this, we will need to charge VAT on our services and will not be able to issue reverse charge invoices.'
        ),
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': ''}),
        required=False,
    )

    invoice_voucher = forms.CharField(
        label=_('Invoice Voucher'),
        help_text=_('If you have a voucher code, enter it here.'),
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': ''}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.pop('organizer', None)
        self.warning_message = None
        super().__init__(*args, **kwargs)
        selected_languages = [
            (code, name)
            for code, name in settings.LANGUAGES
            if code in self.organizer.settings.locales
        ]
        self.fields['preferred_language'].choices = selected_languages
        self.fields['preferred_language'].initial = self.organizer.settings.locale
        self.set_initial_data()

    def set_initial_data(self):
        billing_settings = OrganizerBillingModel.objects.filter(
            organizer_id=self.organizer.id
        ).first()

        if billing_settings:
            for field in self.Meta.fields:
                self.initial[field] = getattr(billing_settings, field, '')

    def validate_vat_number(self, country_code, vat_number):
        if country_code not in pyvat.VAT_REGISTRIES:
            country_name = get_country_name(country_code)
            self.warning_message = _(
                'VAT number validation is not supported for {}'.format(country_name)
            )
            return True
        result = pyvat.is_vat_number_format_valid(vat_number, country_code)
        return result

    def clean_invoice_voucher(self):
        voucher_code = self.cleaned_data['invoice_voucher']
        if not voucher_code:
            return None

        voucher_instance = InvoiceVoucher.objects.filter(code=voucher_code).first()
        if not voucher_instance:
            raise forms.ValidationError('Voucher code not found!')

        if not voucher_instance.is_active():
            raise forms.ValidationError(
                'The voucher code has either expired or reached its usage limit.'
            )

        if voucher_instance.limit_organizer.exists():
            limit_organizer = voucher_instance.limit_organizer.values_list(
                'id', flat=True
            )
            if self.organizer.id not in limit_organizer:
                raise forms.ValidationError(
                    'Voucher code is not valid for this organizer!'
                )

        return voucher_instance

    def clean(self):
        cleaned_data = super().clean()
        country_code = cleaned_data.get('country')
        vat_number = cleaned_data.get('tax_id')

        if vat_number and country_code:
            country_name = get_country_name(country_code)
            is_valid_vat_number = self.validate_vat_number(country_code, vat_number)
            if not is_valid_vat_number:
                self.add_error(
                    'tax_id', _('Invalid VAT number for {}'.format(country_name))
                )

    def save(self, commit=True):
        def set_attribute(instance):
            for field in self.Meta.fields:
                setattr(instance, field, self.cleaned_data[field])

        instance = OrganizerBillingModel.objects.filter(
            organizer_id=self.organizer.id
        ).first()

        if instance:
            set_attribute(instance)
            if commit:
                update_customer_info(
                    instance.stripe_customer_id,
                    email=self.cleaned_data.get('primary_contact_email'),
                    name=self.cleaned_data.get('primary_contact_name'),
                )
                instance.save()
        else:
            instance = OrganizerBillingModel(organizer_id=self.organizer.id)
            set_attribute(instance)
            if commit:
                stripe_customer = create_stripe_customer(
                    email=self.cleaned_data.get('primary_contact_email'),
                    name=self.cleaned_data.get('primary_contact_name'),
                )
                instance.stripe_customer_id = stripe_customer.id
                instance.save()
        return instance
