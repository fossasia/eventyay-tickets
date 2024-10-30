from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from pretix.base.forms import I18nModelForm
from pretix.base.models.organizer import Organizer, OrganizerBillingModel
from pretix.control.utils import create_stripe_customer, update_customer_info
from pretix.helpers.countries import CachedCountries


class OrganizerForm(I18nModelForm):
    error_messages = {
        'duplicate_slug': _("This slug is already in use. Please choose a different one."),
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
            "primary_contact_name",
            "primary_contact_email",
            "company_or_organization_name",
            "address_line_1",
            "address_line_2",
            "zip_code",
            "city",
            "country",
            "preferred_language",
            "tax_id",
        ]

    primary_contact_name = forms.CharField(
        label=_("Primary Contact Name"),
        help_text=_(
            "Please provide your name or the name of the person responsible for this account in your organization."
        ),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": ""}),
    )

    primary_contact_email = forms.EmailField(
        label=_("Primary Contact Email"),
        help_text=_(
            "We will use this email address for all communication related to your contract and billing, "
            "as well as for important updates about your account and our services."
        ),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": ""}),
    )

    company_or_organization_name = forms.CharField(
        label=_("Company or Organization Name"),
        help_text=_("Enter your organization’s legal name."),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": ""}),
    )

    address_line_1 = forms.CharField(
        label=_("Address Line 1"),
        help_text=_("Street address or P.O. box."),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": ""}),
    )

    address_line_2 = forms.CharField(
        label=_("Address Line 2"),
        help_text=_("Apartment, suite, unit, etc. (optional)."),
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": ""}),
    )

    zip_code = forms.CharField(
        label=_("Zip Code"),
        help_text=_("Enter your postal code."),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": ""}),
    )

    city = forms.CharField(
        label=_("City"),
        help_text=_("Enter your city."),
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": ""}),
    )

    country = forms.ChoiceField(
        label=_("Country"),
        help_text=_("Select your country."),
        required=True,
        choices=CachedCountries(),
        initial="US",
    )

    preferred_language = forms.ChoiceField(
        label=_("Preferred Language for Correspondence"),
        help_text=_("Select your preferred language for all communication."),
        required=True,
    )

    tax_id = forms.CharField(
        label=_("Tax ID (e.g., VAT, GST)"),
        help_text=_(
            "If you are located in the EU, please provide your VAT ID. "
            "Without this, we will need to charge VAT on our services and will not be able to issue reverse charge invoices."
        ),
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": ""}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.pop("organizer", None)
        selected_languages = [
            (code, name)
            for code, name in settings.LANGUAGES
            if code in self.organizer.settings.locales
        ]
        self.base_fields["preferred_language"].choices = selected_languages
        self.base_fields["preferred_language"].initial = self.organizer.settings.locale
        super().__init__(*args, **kwargs)
        self.set_initial_data()

    def set_initial_data(self):
        billing_settings = OrganizerBillingModel.objects.filter(
            organizer_id=self.organizer.id
        ).first()

        if billing_settings:
            for field in self.Meta.fields:
                self.initial[field] = getattr(billing_settings, field, "")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.organizer_id = self.organizer.id
        billing_settings = OrganizerBillingModel.objects.filter(
            organizer_id=self.organizer.id
        ).first()

        if billing_settings:
            for field in self.Meta.fields:
                setattr(billing_settings, field, self.cleaned_data[field])
            if commit:
                update_customer_info(
                    billing_settings.stripe_customer_id,
                    email=self.cleaned_data.get("primary_contact_email"),
                    name=self.cleaned_data.get("primary_contact_name"),
                )
                billing_settings.save()
            return billing_settings
        else:
            if commit:
                stripe_customer = create_stripe_customer(email=self.cleaned_data.get("primary_contact_email"),
                                                         name=self.cleaned_data.get("primary_contact_name"))
                instance.stripe_customer_id = stripe_customer.id
                instance.save()
            return instance
