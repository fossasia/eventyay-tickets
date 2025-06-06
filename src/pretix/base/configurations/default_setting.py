import json
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.files import File
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.utils.text import format_lazy
from django.utils.translation import (
    gettext_lazy as _,
)
from django.utils.translation import (
    gettext_noop,
    pgettext,
    pgettext_lazy,
)
from i18nfield.forms import I18nFormField, I18nTextarea, I18nTextInput
from i18nfield.strings import LazyI18nString
from rest_framework import serializers

from pretix.api.serializers.fields import (
    ListMultipleChoiceField,
    UploadedFileField,
)
from pretix.api.serializers.i18n import I18nField, I18nURLField
from pretix.base.configurations.lazy_i18n_string_list_base import (
    LazyI18nStringList,
)
from pretix.base.forms import I18nURLFormField
from pretix.base.models.tax import TaxRule
from pretix.base.reldate import (
    RelativeDateField,
    RelativeDateTimeField,
    RelativeDateWrapper,
    SerializerRelativeDateField,
    SerializerRelativeDateTimeField,
)
from pretix.control.forms import (
    ExtFileField,
    FontSelect,
    MultipleLanguagesWidget,
    SingleLanguageWidget,
)
from pretix.helpers.countries import CachedCountries


def country_choice_kwargs():
    allcountries = list(CachedCountries())
    allcountries.insert(0, ('', _('Select country')))
    return {'choices': allcountries}


def primary_font_kwargs():
    from pretix.presale.style import get_fonts

    choices = [('Open Sans', 'Open Sans')]
    choices += [(a, {'title': a, 'data': v}) for a, v in get_fonts().items()]
    return {
        'choices': choices,
    }


DEFAULT_SETTINGS = {
    'max_items_per_order': {
        'default': '10',
        'type': int,
        'form_class': forms.IntegerField,
        'serializer_class': serializers.IntegerField,
        'form_kwargs': dict(
            min_value=1,
            label=_('Maximum number of items per order'),
            help_text=_('Add-on products will be excluded from the count.'),
        ),
    },
    'display_net_prices': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Display net prices in the product list instead of gross prices (not recommended)'),
            help_text=_(
                'Regardless of your selection, the cart will display gross prices as this is the final amount to be '
                'paid.'
            ),
        ),
    },
    'system_question_order': {
        'default': {},
        'type': dict,
    },
    'attendee_names_asked': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Require attendee names'),
            help_text=_('Require attendee names for all tickets which include admission to the event.'),
        ),
    },
    'attendee_names_required': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Require attendee names'),
            help_text=_('Require attendees to fill in their names for all admission tickets.'),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_settings-attendee_names_asked'}),
        ),
    },
    'attendee_emails_asked': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for email addresses per ticket'),
            help_text=_(
                'Normally, eventyay asks for one email address per order and the order confirmation will be sent '
                'only to that email address. If you enable this option, the system will additionally ask for '
                'individual email addresses for every admission ticket. This might be useful if you want to '
                'obtain individual addresses for every attendee even in case of group orders. However, '
                'eventyay will send the order confirmation by default only to the primary email address, not to '
                'the per-attendee addresses. You can however enable this in the E-mail settings.'
            ),
        ),
    },
    'attendee_emails_required': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Require email addresses per ticket'),
            help_text=_(
                'Require attendees to fill in individual e-mail addresses for all admission tickets. See the '
                'above option for more details. One email address for the order confirmation will always be '
                'required regardless of this setting.'
            ),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_settings-attendee_emails_asked'}),
        ),
    },
    'attendee_company_asked': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for company per ticket'),
        ),
    },
    'attendee_company_required': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Require company per ticket'),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_settings-attendee_company_asked'}),
        ),
    },
    'attendee_addresses_asked': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for postal addresses per ticket'),
        ),
    },
    'attendee_addresses_required': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Require postal addresses per ticket'),
            help_text=_('Require attendees to fill in postal addresses for all admission tickets.'),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_settings-attendee_addresses_asked'}),
        ),
    },
    'order_email_asked_twice': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for the order email address twice'),
            help_text=_('Require attendees to enter their primary email address twice to help prevent errors.'),
        ),
    },
    'order_phone_asked': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for a phone number per order'),
        ),
    },
    'order_phone_required': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Require a phone number per order'),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_settings-order_phone_asked'}),
        ),
    },
    'invoice_address_asked': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for invoice address'),
        ),
    },
    'invoice_address_not_asked_free': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Do not ask for invoice address if an order is free of charge.'),
        ),
    },
    'invoice_name_required': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Require attendee name'),
        ),
    },
    'invoice_attendee_name': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Show attendee names on invoices'),
        ),
    },
    'invoice_eu_currencies': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_(
                'On invoices from one EU country to another EU country with a different currency, display the tax '
                'amounts in both currencies.'
            ),
        ),
    },
    'invoice_address_required': {
        'default': 'False',
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'type': bool,
        'form_kwargs': dict(
            label=_('Require invoice address'),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_invoice_address_asked'}),
        ),
    },
    'invoice_address_company_required': {
        'default': 'False',
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'type': bool,
        'form_kwargs': dict(
            label=_('Require a business addresses'),
            help_text=_('This will require attendees to enter a company name.'),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_invoice_address_required'}),
        ),
    },
    'invoice_address_beneficiary': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for beneficiary'),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_invoice_address_asked'}),
        ),
    },
    'invoice_address_custom_field': {
        'default': '',
        'type': LazyI18nString,
        'form_class': I18nFormField,
        'serializer_class': I18nField,
        'form_kwargs': dict(
            label=_('Custom address field'),
            widget=I18nTextInput,
            help_text=_(
                'If you want to add a custom text field, such as a country-specific registration number, '
                'to your invoice address form, please enter the label here. This label will be used both for '
                'prompting the user to input their details and for displaying the value on the invoice. The field '
                'will be optional.'
            ),
        ),
    },
    'invoice_address_vatid': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for VAT ID'),
            help_text=_(
                'This option is only applicable if an invoice address is requested. The VAT ID field will not be '
                'required.'
            ),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_invoice_address_asked'}),
        ),
    },
    'invoice_address_explanation_text': {
        'default': '',
        'type': LazyI18nString,
        'form_class': I18nFormField,
        'serializer_class': I18nField,
        'form_kwargs': dict(
            label=_('Invoice address explanation'),
            widget=I18nTextarea,
            widget_kwargs={'attrs': {'rows': '2'}},
            help_text=_('This text will be shown above the invoice address form during checkout.'),
        ),
    },
    'invoice_show_payments': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Show paid amount on partially paid invoices'),
            help_text=_(
                'If an invoice has already been paid partially, this option will add the paid and pending '
                'amount to the invoice.'
            ),
        ),
    },
    'invoice_include_free': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Show free products on invoices'),
            help_text=_('Note that invoices will never be generated for orders that contain only free products.'),
        ),
    },
    'invoice_include_expire_date': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Show expiration date of order'),
            help_text=_('The expiration date will not be shown if the invoice is generated after the order is paid.'),
        ),
    },
    'invoice_numbers_counter_length': {
        'default': '5',
        'type': int,
        'form_class': forms.IntegerField,
        'serializer_class': serializers.IntegerField,
        'form_kwargs': dict(
            label=_('Minimum length of invoice number after prefix'),
            help_text=_(
                'The part of your invoice number after your prefix will be filled up with leading zeros up to this '
                'length, e.g. INV-001 or INV-00001.'
            ),
        ),
    },
    'invoice_numbers_consecutive': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Generate invoices with consecutive numbers'),
            help_text=_('If deactivated, the order code will be used in the invoice number.'),
        ),
    },
    'invoice_numbers_prefix': {
        'default': '',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            label=_('Invoice number prefix'),
            help_text=_(
                'This will be prepended to invoice numbers. If you leave this field empty, your event slug will '
                'be used followed by a dash. Attention: If multiple events within the same organization use the '
                'same value in this field, they will share their number range, i.e. every full number will be '
                'used at most once over all of your events. This setting only affects future invoices. You can '
                'use %Y (with century) %y (without century) to insert the year of the invoice, or %m and %d for '
                'the day of month.'
            ),
        ),
    },
    'invoice_numbers_prefix_cancellations': {
        'default': '',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            label=_('Invoice number prefix for cancellations'),
            help_text=_(
                'This will be prepended to invoice numbers of cancellations. If you leave this field empty, '
                'the same numbering scheme will be used that you configured for regular invoices.'
            ),
        ),
    },
    'invoice_renderer': {
        'default': 'classic',
        'type': str,
    },
    'ticket_secret_generator': {
        'default': 'random',
        'type': str,
    },
    'reservation_time': {
        'default': '30',
        'type': int,
        'form_class': forms.IntegerField,
        'serializer_class': serializers.IntegerField,
        'form_kwags': dict(
            min_value=0,
            label=_('Reservation period'),
            help_text=_("The number of minutes the items in a user's cart are reserved for this user."),
        ),
    },
    'redirect_to_checkout_directly': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Directly redirect to check-out after a product has been added to the cart.'),
        ),
    },
    'presale_has_ended_text': {
        'default': '',
        'type': LazyI18nString,
        'form_class': I18nFormField,
        'serializer_class': I18nField,
        'form_kwargs': dict(
            label=_('End of presale text'),
            widget=I18nTextarea,
            widget_kwargs={'attrs': {'rows': '2'}},
            help_text=_(
                'This text will be shown above the ticket shop once the designated sales timeframe for this event '
                'is over. You can use it to describe other options to get a ticket, such as a box office.'
            ),
        ),
    },
    'payment_explanation': {
        'default': '',
        'type': LazyI18nString,
        'form_class': I18nFormField,
        'serializer_class': I18nField,
        'form_kwargs': dict(
            widget=I18nTextarea,
            widget_kwargs={
                'attrs': {
                    'rows': 3,
                }
            },
            label=_('Guidance text'),
            help_text=_(
                'This text will be shown above the payment options. You can explain the choices to the user here, '
                'if you want.'
            ),
        ),
    },
    'payment_term_mode': {
        'default': 'days',
        'type': str,
        'form_class': forms.ChoiceField,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': dict(
            choices=(('days', _('in days')), ('minutes', _('in minutes'))),
        ),
        'form_kwargs': dict(
            label=_('Set payment term'),
            widget=forms.RadioSelect,
            choices=(('days', _('in days')), ('minutes', _('in minutes'))),
            help_text=_(
                'If using days, the order will expire at the end of the last day. '
                'Using minutes is more exact, but should only be used for real-time payment methods.'
            ),
        ),
    },
    'payment_term_days': {
        'default': '14',
        'type': int,
        'form_class': forms.IntegerField,
        'serializer_class': serializers.IntegerField,
        'form_kwargs': dict(
            label=_('Payment term in days'),
            widget=forms.NumberInput(
                attrs={
                    'data-display-dependency': '#id_payment_term_mode_0',
                    'data-required-if': '#id_payment_term_mode_0',
                },
            ),
            help_text=_(
                'The number of days after placing an order the user has to pay to preserve their reservation. If '
                'you use slow payment methods like bank transfer, we recommend 14 days. If you only use real-time '
                'payment methods, we recommend still setting two or three days to allow people to retry failed '
                'payments.'
            ),
            validators=[MinValueValidator(0), MaxValueValidator(1000000)],
        ),
        'serializer_kwargs': dict(validators=[MinValueValidator(0), MaxValueValidator(1000000)]),
    },
    'payment_term_weekdays': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Only end payment terms on weekdays'),
            help_text=_(
                'If this is activated and the payment term of any order ends on a Saturday or Sunday, it will be '
                'moved to the next Monday instead. This is required in some countries by civil law. This will '
                'not effect the last date of payments configured below.'
            ),
            widget=forms.CheckboxInput(
                attrs={
                    'data-display-dependency': '#id_payment_term_mode_0',
                },
            ),
        ),
    },
    'payment_term_minutes': {
        'default': '30',
        'type': int,
        'form_class': forms.IntegerField,
        'serializer_class': serializers.IntegerField,
        'form_kwargs': dict(
            label=_('Payment term in minutes'),
            help_text=_(
                'The number of minutes after placing an order the user has to pay to preserve their reservation. '
                'Only use this if you exclusively offer real-time payment methods. Please note that for technical '
                'reasons, the actual time frame might be a few minutes longer before the order is marked as expired.'
            ),
            validators=[MinValueValidator(0), MaxValueValidator(1440)],
            widget=forms.NumberInput(
                attrs={
                    'data-display-dependency': '#id_payment_term_mode_1',
                    'data-required-if': '#id_payment_term_mode_1',
                },
            ),
        ),
        'serializer_kwargs': dict(validators=[MinValueValidator(0), MaxValueValidator(1440)]),
    },
    'payment_term_last': {
        'default': None,
        'type': RelativeDateWrapper,
        'form_class': RelativeDateField,
        'serializer_class': SerializerRelativeDateField,
        'form_kwargs': dict(
            label=_('Last date of payments'),
            help_text=_(
                'The last date any payments are accepted. This has precedence over the terms '
                'configured above. If you use the event series feature and an order contains tickets for '
                'multiple dates, the earliest date will be used.'
            ),
        ),
    },
    'payment_term_expire_automatically': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Automatically expire unpaid orders'),
            help_text=_(
                "If checked, all unpaid orders will automatically go from 'pending' to 'expired' "
                'after the end of their payment deadline. This means that those tickets go back to '
                'the pool and can be ordered by other people.'
            ),
        ),
    },
    'payment_pending_hidden': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Hide "payment pending" state on attendee-facing pages'),
            help_text=_(
                'The payment instructions panel will still be shown to the primary attendee, but no indication '
                'of missing payment will be visible on the ticket pages of attendees who did not buy the ticket '
                'themselves.'
            ),
        ),
    },
    'payment_giftcard__enabled': {'default': 'True', 'type': bool},
    'payment_resellers__restrict_to_sales_channels': {
        'default': ['resellers'],
        'type': list,
    },
    'payment_term_accept_late': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Accept late payments'),
            help_text=_(
                "Accept payments for orders even when they are in 'expired' state as long as enough "
                "capacity is available. No payments will ever be accepted after the 'Last date of payments' "
                'configured above.'
            ),
        ),
    },
    'presale_start_show_date': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Show start date'),
            help_text=_('Show the presale start date before presale has started.'),
            widget=forms.CheckboxInput,
        ),
    },
    'tax_rate_default': {'default': None, 'type': TaxRule},
    'invoice_generate': {
        'default': 'False',
        'type': str,
        'form_class': forms.ChoiceField,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': dict(
            choices=(
                ('False', _('Do not generate invoices')),
                ('admin', _('Only manually in admin panel')),
                ('user', _('Automatically on user request')),
                ('True', _('Automatically for all created orders')),
                (
                    'paid',
                    _('Automatically on payment or when required by payment method'),
                ),
            ),
        ),
        'form_kwargs': dict(
            label=_('Generate invoices'),
            widget=forms.RadioSelect,
            choices=(
                ('False', _('Do not generate invoices')),
                ('admin', _('Only manually in admin panel')),
                ('user', _('Automatically on user request')),
                ('True', _('Automatically for all created orders')),
                (
                    'paid',
                    _('Automatically on payment or when required by payment method'),
                ),
            ),
            help_text=_('Invoices will never be automatically generated for free orders.'),
        ),
    },
    'invoice_reissue_after_modify': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Automatically cancel and reissue invoice on address changes'),
            help_text=_(
                'If attendees change their invoice address on an existing order, the invoice will '
                'automatically be canceled and a new invoice will be issued. This setting does not affect '
                'changes made through the backend.'
            ),
        ),
    },
    'invoice_generate_sales_channels': {'default': json.dumps(['web']), 'type': list},
    'invoice_address_from': {
        'default': '',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            label=_('Address line'),
            widget=forms.Textarea(attrs={'rows': 2, 'placeholder': _('Albert Einstein Road 52')}),
        ),
    },
    'invoice_address_from_name': {
        'default': '',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            label=_('Company name'),
        ),
    },
    'invoice_address_from_zipcode': {
        'default': '',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            widget=forms.TextInput(attrs={'placeholder': '12345'}),
            label=_('ZIP code'),
        ),
    },
    'invoice_address_from_city': {
        'default': '',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            widget=forms.TextInput(attrs={'placeholder': _('Random City')}),
            label=_('City'),
        ),
    },
    'invoice_address_from_country': {
        'default': '',
        'type': str,
        'form_class': forms.ChoiceField,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': lambda: dict(**country_choice_kwargs()),
        'form_kwargs': lambda: dict(label=_('Country'), **country_choice_kwargs()),
    },
    'invoice_address_from_tax_id': {
        'default': '',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            label=_('Domestic tax ID'),
            help_text=_('e.g. tax number in Germany, ABN in Australia, …'),
        ),
    },
    'invoice_address_from_vat_id': {
        'default': '',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            label=_('EU VAT ID'),
        ),
    },
    'invoice_introductory_text': {
        'default': '',
        'type': LazyI18nString,
        'form_class': I18nFormField,
        'serializer_class': I18nField,
        'form_kwargs': dict(
            widget=I18nTextarea,
            widget_kwargs={
                'attrs': {
                    'rows': 3,
                    'placeholder': _('e.g. With this document, we sent you the invoice for your ticket order.'),
                }
            },
            label=_('Introductory text'),
            help_text=_('Will be printed on every invoice above the invoice rows.'),
        ),
    },
    'invoice_additional_text': {
        'default': '',
        'type': LazyI18nString,
        'form_class': I18nFormField,
        'serializer_class': I18nField,
        'form_kwargs': dict(
            widget=I18nTextarea,
            widget_kwargs={
                'attrs': {
                    'rows': 3,
                    'placeholder': _(
                        'e.g. Thank you for your purchase! You can find more information on the event at ...'
                    ),
                }
            },
            label=_('Additional text'),
            help_text=_('Will be printed on every invoice below the invoice total.'),
        ),
    },
    'invoice_footer_text': {
        'default': '',
        'type': LazyI18nString,
        'form_class': I18nFormField,
        'serializer_class': I18nField,
        'form_kwargs': dict(
            widget=I18nTextarea,
            widget_kwargs={
                'attrs': {
                    'rows': 5,
                    'placeholder': _(
                        'e.g. your bank details, legal details like your VAT ID, registration numbers, etc.'
                    ),
                }
            },
            label=_('Footer'),
            help_text=_('Will be printed centered and in a smaller font at the end of every invoice page.'),
        ),
    },
    'invoice_language': {'default': '__user__', 'type': str},
    'invoice_email_attachment': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Attach invoices to emails'),
            help_text=_(
                'If invoices are automatically generated for all orders, they will be attached to the order '
                'confirmation mail. If they are automatically generated on payment, they will be attached to the '
                'payment confirmation mail. If they are not automatically generated, they will not be attached '
                'to emails.'
            ),
        ),
    },
    'show_items_outside_presale_period': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Show items outside presale period'),
            help_text=_('Show item details before presale has started and after presale has ended'),
        ),
    },
    'timezone': {'default': settings.TIME_ZONE, 'type': str},
    'locales': {
        'default': json.dumps([settings.LANGUAGE_CODE]),
        'type': list,
        'serializer_class': ListMultipleChoiceField,
        'serializer_kwargs': dict(
            choices=settings.LANGUAGES,
            required=True,
        ),
        'form_class': forms.MultipleChoiceField,
        'form_kwargs': dict(
            choices=settings.LANGUAGES,
            widget=MultipleLanguagesWidget,
            required=True,
            label=_('Available languages'),
        ),
    },
    'locale': {
        'default': settings.LANGUAGE_CODE,
        'type': str,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': dict(
            choices=settings.LANGUAGES,
            required=True,
        ),
        'form_class': forms.ChoiceField,
        'form_kwargs': dict(
            choices=settings.LANGUAGES,
            widget=SingleLanguageWidget,
            required=True,
            label=_('Default language'),
        ),
    },
    'region': {
        'default': None,
        'type': str,
        'form_class': forms.ChoiceField,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': lambda: dict(**country_choice_kwargs()),
        'form_kwargs': lambda: dict(
            label=_('Region'),
            help_text=_(
                'Will be used to determine date and time formatting as well as default country for attendee '
                'addresses and phone numbers. For formatting, this takes less priority than the language and '
                'is therefore mostly relevant for languages used in different regions globally (like English).'
            ),
            **country_choice_kwargs(),
        ),
    },
    'show_dates_on_frontpage': {
        'default': 'True',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Show event times and dates on the ticket shop'),
            help_text=_(
                "If disabled, no date or time will be shown on the ticket shop's front page. This settings "
                'does however not affect the display in other locations.'
            ),
        ),
    },
    'show_date_to': {
        'default': 'True',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Show event end date'),
            help_text=_("If disabled, only event's start date will be displayed to the public."),
        ),
    },
    'show_times': {
        'default': 'True',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Show dates with time'),
            help_text=_("If disabled, the event's start and end date will be displayed without the time of day."),
        ),
    },
    'hide_sold_out': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Hide all products that are sold out'),
        ),
    },
    'show_quota_left': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Show number of tickets left'),
            help_text=_('Publicly show how many tickets of a certain type are still available.'),
        ),
    },
    'meta_noindex': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Ask search engines not to index the ticket shop'),
        ),
    },
    'show_variations_expanded': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Show variations of a product expanded by default'),
        ),
    },
    'waiting_list_enabled': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Enable waiting list'),
            help_text=_(
                'Once a ticket is sold out, people can add themselves to a waiting list. As soon as a ticket '
                'becomes available again, it will be reserved for the first person on the waiting list and this '
                'person will receive an email notification with a voucher that can be used to buy a ticket.'
            ),
        ),
    },
    'waiting_list_auto': {
        'default': 'True',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Automatic waiting list assignments'),
            help_text=_(
                'If ticket capacity becomes free, automatically create a voucher and send it to the first person '
                'on the waiting list for that product. If this is not active, mails will not be send automatically '
                'but you can send them manually via the control panel. If you disable the waiting list but keep '
                'this option enabled, tickets will still be sent out.'
            ),
            widget=forms.CheckboxInput(),
        ),
    },
    'waiting_list_hours': {
        'default': '48',
        'type': int,
        'serializer_class': serializers.IntegerField,
        'form_class': forms.IntegerField,
        'form_kwargs': dict(
            label=_('Waiting list response time'),
            min_value=1,
            help_text=_(
                'If a ticket voucher is sent to a person on the waiting list, it has to be redeemed within this '
                'number of hours until it expires and can be re-assigned to the next person on the list.'
            ),
            widget=forms.NumberInput(),
        ),
    },
    'waiting_list_names_asked': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for a name'),
            help_text=_('Ask for a name when signing up to the waiting list.'),
        ),
    },
    'waiting_list_names_required': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Require name'),
            help_text=_('Require a name when signing up to the waiting list..'),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_settings-waiting_list_names_asked'}),
        ),
    },
    'waiting_list_phones_asked': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Ask for a phone number'),
            help_text=_('Ask for a phone number when signing up to the waiting list.'),
        ),
    },
    'waiting_list_phones_required': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Require phone number'),
            help_text=_('Require a phone number when signing up to the waiting list..'),
            widget=forms.CheckboxInput(attrs={'data-checkbox-dependency': '#id_settings-waiting_list_phones_asked'}),
        ),
    },
    'waiting_list_phones_explanation_text': {
        'default': '',
        'type': LazyI18nString,
        'form_class': I18nFormField,
        'serializer_class': I18nField,
        'form_kwargs': dict(
            label=_('Phone number explanation'),
            widget=I18nTextarea,
            widget_kwargs={'attrs': {'rows': '2'}},
            help_text=_(
                'If you ask for a phone number, explain why you do so and what you will use the phone number for.'
            ),
        ),
    },
    'ticket_download': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Allow users to download tickets'),
            help_text=_('If this is off, nobody can download a ticket.'),
        ),
    },
    'ticket_download_date': {
        'default': None,
        'type': RelativeDateWrapper,
        'form_class': RelativeDateTimeField,
        'serializer_class': SerializerRelativeDateTimeField,
        'form_kwargs': dict(
            label=_('Download date'),
            help_text=_(
                'Ticket download will be offered after this date. If you use the event series feature and an order '
                'contains tickets for multiple event dates, download of all tickets will be available if at least '
                'one of the event dates allows it.'
            ),
        ),
    },
    'ticket_download_addons': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Generate tickets for add-on products'),
            help_text=_(
                'By default, tickets are only issued for products selected individually, not for add-on '
                'products. With this option, a separate ticket is issued for every add-on product as well.'
            ),
            widget=forms.CheckboxInput(
                attrs={
                    'data-checkbox-dependency': '#id_ticket_download',
                    'data-checkbox-dependency-visual': 'on',
                }
            ),
        ),
    },
    'ticket_download_nonadm': {
        'default': 'True',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Generate tickets for all products'),
            help_text=_(
                'If turned off, tickets are only issued for products that are marked as an "admission ticket"'
                'in the product settings. You can also turn off ticket issuing in every product separately.'
            ),
            widget=forms.CheckboxInput(
                attrs={
                    'data-checkbox-dependency': '#id_ticket_download',
                    'data-checkbox-dependency-visual': 'on',
                }
            ),
        ),
    },
    'ticket_download_pending': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Generate tickets for pending orders'),
            help_text=_('If turned off, ticket downloads are only possible after an order has been marked as paid.'),
            widget=forms.CheckboxInput(
                attrs={
                    'data-checkbox-dependency': '#id_ticket_download',
                    'data-checkbox-dependency-visual': 'on',
                }
            ),
        ),
    },
    'ticket_download_require_validated_email': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Do not issue ticket before email address is validated'),
            help_text=_(
                'If turned on, tickets will not be offered for download directly after purchase. They will '
                'be attached to the payment confirmation email (if the file size is not too large), and the '
                'attendee will be able to download them from the page as soon as they clicked a link in '
                'the email. Does not affect orders performed through other sales channels.'
            ),
        ),
    },
    'require_registered_account_for_tickets': {
        'default': 'False',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Only allow registered accounts to get a ticket'),
            help_text=_(
                'If this option is turned on, only registered accounts will be allowed to purchase tickets. The '
                "'Continue as a Guest' option will not be available for attendees."
            ),
        ),
    },
    'event_list_availability': {
        'default': 'True',
        'type': bool,
        'serializer_class': serializers.BooleanField,
        'form_class': forms.BooleanField,
        'form_kwargs': dict(
            label=_('Show availability in event overviews'),
            help_text=_(
                'If checked, the list of events will show if events are sold out. This might '
                'make for longer page loading times if you have lots of events and the shown status might be out '
                'of date for up to two minutes.'
            ),
            required=False,
        ),
    },
    'event_list_type': {
        'default': 'list',
        'type': str,
        'form_class': forms.ChoiceField,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': dict(
            choices=(
                ('list', _('List')),
                ('week', _('Week calendar')),
                ('calendar', _('Month calendar')),
            )
        ),
        'form_kwargs': dict(
            label=_('Default overview style'),
            choices=(
                ('list', _('List')),
                ('week', _('Week calendar')),
                ('calendar', _('Month calendar')),
            ),
            help_text=_(
                'If your event series has more than 50 dates in the future, only the month or week calendar can be '
                'used.'
            ),
        ),
    },
    'event_list_available_only': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Hide all unavailable dates from calendar or list views'),
        ),
    },
    'allow_modifications_after_checkin': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Allow attendees to modify their information after they checked in.'),
        ),
    },
    'last_order_modification_date': {
        'default': None,
        'type': RelativeDateWrapper,
        'form_class': RelativeDateTimeField,
        'serializer_class': SerializerRelativeDateTimeField,
        'form_kwargs': dict(
            label=_('Last date of modifications'),
            help_text=_(
                'The last date users can modify details of their orders, such as attendee names or '
                'answers to questions. If you use the event series feature and an order contains tickets for '
                'multiple event dates, the earliest date will be used.'
            ),
        ),
    },
    'change_allow_user_variation': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Customers can change the variation of the products they purchased'),
        ),
    },
    'change_allow_user_price': {
        'default': 'gte',
        'type': str,
        'form_class': forms.ChoiceField,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': dict(
            choices=(
                (
                    'gte',
                    _('Only allow changes if the resulting price is higher or equal than the previous price.'),
                ),
                (
                    'gt',
                    _('Only allow changes if the resulting price is higher than the previous price.'),
                ),
                (
                    'eq',
                    _('Only allow changes if the resulting price is equal to the previous price.'),
                ),
                (
                    'any',
                    _('Allow changes regardless of price, even if this results in a refund.'),
                ),
            )
        ),
        'form_kwargs': dict(
            label=_('Requirement for changed prices'),
            choices=(
                (
                    'gte',
                    _('Only allow changes if the resulting price is higher or equal than the previous price.'),
                ),
                (
                    'gt',
                    _('Only allow changes if the resulting price is higher than the previous price.'),
                ),
                (
                    'eq',
                    _('Only allow changes if the resulting price is equal to the previous price.'),
                ),
                (
                    'any',
                    _('Allow changes regardless of price, even if this results in a refund.'),
                ),
            ),
            widget=forms.RadioSelect,
        ),
    },
    'change_allow_user_until': {
        'default': None,
        'type': RelativeDateWrapper,
        'form_class': RelativeDateTimeField,
        'serializer_class': SerializerRelativeDateTimeField,
        'form_kwargs': dict(
            label=_('Do not allow changes after'),
        ),
    },
    'cancel_allow_user': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Customers can cancel their unpaid orders'),
        ),
    },
    'cancel_allow_user_until': {
        'default': None,
        'type': RelativeDateWrapper,
        'form_class': RelativeDateTimeField,
        'serializer_class': SerializerRelativeDateTimeField,
        'form_kwargs': dict(
            label=_('Do not allow cancellations after'),
        ),
    },
    'cancel_allow_user_paid': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Customers can cancel their paid orders'),
            help_text=_(
                'Paid money will be automatically paid back if the payment method allows it. '
                'Otherwise, a manual refund will be created for you to process manually.'
            ),
        ),
    },
    'cancel_allow_user_paid_keep': {
        'default': '0.00',
        'type': Decimal,
        'form_class': forms.DecimalField,
        'serializer_class': serializers.DecimalField,
        'serializer_kwargs': dict(max_digits=10, decimal_places=2),
        'form_kwargs': dict(
            label=_('Keep a fixed cancellation fee'),
        ),
    },
    'cancel_allow_user_paid_keep_fees': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Keep payment, shipping and service fees'),
        ),
    },
    'cancel_allow_user_paid_keep_percentage': {
        'default': '0.00',
        'type': Decimal,
        'form_class': forms.DecimalField,
        'serializer_class': serializers.DecimalField,
        'serializer_kwargs': dict(max_digits=10, decimal_places=2),
        'form_kwargs': dict(
            label=_('Keep a percentual cancellation fee'),
        ),
    },
    'cancel_allow_user_paid_adjust_fees': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Allow attendees to voluntarily choose a lower refund'),
            help_text=_('With this option enabled, your attendees can choose to get a smaller refund to support you.'),
        ),
    },
    'cancel_allow_user_paid_adjust_fees_explanation': {
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                'However, if you want us to help keep the lights on here, please consider using the slider below to '
                'request a smaller refund. Thank you!'
            )
        ),
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Voluntary lower refund explanation'),
            widget=I18nTextarea,
            widget_kwargs={'attrs': {'rows': '2'}},
            help_text=_(
                'This text will be shown in between the explanation of how the refunds work and the slider '
                'which your attendees can use to choose the amount they would like to receive. You can use it '
                'e.g. to explain choosing a lower refund will help your organization.'
            ),
        ),
    },
    'cancel_allow_user_paid_adjust_fees_step': {
        'default': None,
        'type': Decimal,
        'form_class': forms.DecimalField,
        'serializer_class': serializers.DecimalField,
        'serializer_kwargs': dict(max_digits=10, decimal_places=2),
        'form_kwargs': dict(
            max_digits=10,
            decimal_places=2,
            label=_('Step size for reduction amount'),
            help_text=_(
                'By default, attendees can choose an arbitrary amount for you to keep. If you set this to e.g. '
                '10, they will only be able to choose values in increments of 10.'
            ),
        ),
    },
    'cancel_allow_user_paid_require_approval': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_(
                'Customers can only request a cancellation that needs to be approved by the event organizer '
                'before the order is canceled and a refund is issued.'
            ),
        ),
    },
    'cancel_allow_user_paid_refund_as_giftcard': {
        'default': 'off',
        'type': str,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': dict(
            choices=[
                ('off', _('All refunds are issued to the original payment method')),
                (
                    'option',
                    _('Customers can choose between a gift card and a refund to their payment method'),
                ),
                ('force', _('All refunds are issued as gift cards')),
            ],
        ),
        'form_class': forms.ChoiceField,
        'form_kwargs': dict(
            label=_('Refund method'),
            choices=[
                ('off', _('All refunds are issued to the original payment method')),
                (
                    'option',
                    _('Customers can choose between a gift card and a refund to their payment method'),
                ),
                ('force', _('All refunds are issued as gift cards')),
            ],
            widget=forms.RadioSelect,
            # When adding a new ordering, remember to also define it in the event model
        ),
    },
    'cancel_allow_user_paid_until': {
        'default': None,
        'type': RelativeDateWrapper,
        'form_class': RelativeDateTimeField,
        'serializer_class': SerializerRelativeDateTimeField,
        'form_kwargs': dict(
            label=_('Do not allow cancellations after'),
        ),
    },
    'contact_mail': {
        'default': None,
        'type': str,
        'serializer_class': serializers.EmailField,
        'form_class': forms.EmailField,
        'form_kwargs': dict(
            label=_('Contact address'),
            help_text=_("We'll show this publicly to allow attendees to contact you."),
        ),
    },
    'imprint_url': {
        'default': None,
        'type': str,
        'form_class': forms.URLField,
        'form_kwargs': dict(
            label=_('Imprint URL'),
            help_text=_(
                'This should point e.g. to a part of your website that has your contact details and legal information.'
            ),
        ),
        'serializer_class': serializers.URLField,
    },
    'confirm_texts': {
        'default': LazyI18nStringList(),
        'type': LazyI18nStringList,
        'serializer_class': serializers.ListField,
        'serializer_kwargs': lambda: dict(child=I18nField()),
    },
    'mail_html_renderer': {'default': 'classic', 'type': str},
    'mail_attach_tickets': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Attach ticket files'),
            help_text=format_lazy(
                _("Tickets will never be attached if they're larger than {size} to avoid email delivery problems."),
                size='4 MB',
            ),
        ),
    },
    'mail_attach_ical': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Attach calendar files'),
            help_text=_('If enabled, we will attach an .ics calendar file to order confirmation emails.'),
        ),
    },
    'mail_prefix': {
        'default': None,
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            label=_('Subject prefix'),
            help_text=_(
                'This will be prepended to the subject of all outgoing emails, formatted as [prefix]. '
                'Choose, for example, a short form of your event name.'
            ),
        ),
    },
    'mail_bcc': {'default': None, 'type': str},
    'mail_from': {
        'default': settings.MAIL_FROM,
        'type': str,
        'form_class': forms.EmailField,
        'serializer_class': serializers.EmailField,
        'form_kwargs': dict(
            label=_('Sender address'),
            help_text=_('Sender address for outgoing emails'),
        ),
    },
    'mail_from_name': {
        'default': None,
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'form_kwargs': dict(
            label=_('Sender name'),
            help_text=_(
                'Sender name used in conjunction with the sender address for outgoing emails. '
                'Defaults to your event name.'
            ),
        ),
    },
    'mail_sales_channel_placed_paid': {
        'default': ['web'],
        'type': list,
    },
    'mail_sales_channel_download_reminder': {
        'default': ['web'],
        'type': list,
    },
    'mail_text_signature': {'type': LazyI18nString, 'default': ''},
    'mail_text_resend_link': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

you receive this message because you asked us to send you the link
to your order for {event}.

You can change your order details and view the status of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_resend_all_links': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

somebody requested a list of your orders for {event}.
The list is as follows:

{orders}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_free_attendee': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello {attendee_name},

you have been registered for {event} successfully.

You can view the details and status of your ticket here:
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_free': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

your order for {event} was successful. As you only ordered free products,
no payment is required.

You can change your order details and view the status of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_send_order_free_attendee': {'type': bool, 'default': 'False'},
    'mail_text_order_placed_require_approval': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

we successfully received your order for {event}. Since you ordered
a product that requires approval by the event organizer, we ask you to
be patient and wait for our next email.

You can change your order details and view the status of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_placed': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

we successfully received your order for {event} with a total value
of {total_with_currency}. Please complete your payment before {expire_date}.

{payment_info}

You can change your order details and view the status of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_send_order_placed_attendee': {'type': bool, 'default': 'False'},
    'mail_text_order_placed_attendee': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello {attendee_name},

a ticket for {event} has been ordered for you.

You can view the details and status of your ticket here:
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_changed': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

your order for {event} has been changed.

You can view the status of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_paid': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

we successfully received your payment for {event}. Thank you!

{payment_info}

You can change your order details and view the status of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_send_order_paid_attendee': {'type': bool, 'default': 'False'},
    'mail_text_order_paid_attendee': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello {attendee_name},

a ticket for {event} that has been ordered for you is now paid.

You can view the details and status of your ticket here:
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_days_order_expire_warning': {'type': int, 'default': '3'},
    'mail_text_order_expire_warning': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

we did not yet receive a full payment for your order for {event}.
Please keep in mind that we only guarantee your order if we receive
your payment before {expire_date}.

You can view the payment information and the status of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_waiting_list': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

you submitted yourself to the waiting list for {event},
for the product {product}.

We now have a ticket ready for you! You can redeem it in our ticket shop
within the next {hours} hours by entering the following voucher code:

{code}

Alternatively, you can just click on the following link:

{url}

Please note that this link is only valid within the next {hours} hours!
We will reassign the ticket to the next person on the list if you do not
redeem the voucher within that timeframe.

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_canceled': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

your order {code} for {event} has been canceled.

You can view the details of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_approved': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

we approved your order for {event} and will be happy to welcome you
at our event.

Please continue by paying for your order before {expire_date}.

You can select a payment method and perform the payment here:

{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_approved_free': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

we approved your order for {event} and will be happy to welcome you
at our event. As you only ordered free products, no payment is required.

You can change your order details and view the status of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_denied': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

unfortunately, we denied your order request for {event}.

{comment}

You can view the details of your order here:

{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_text_order_custom_mail': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

You can change your order details and view the status of your order at
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'mail_days_download_reminder': {'type': int, 'default': None},
    'mail_send_download_reminder_attendee': {'type': bool, 'default': 'False'},
    'mail_text_download_reminder_attendee': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello {attendee_name},

    you are registered for {event}.

    If you did not do so already, you can download your ticket here:
    {url}

    Best regards,
    Your {event} team"""
            )
        ),
    },
    'mail_text_download_reminder': {
        'type': LazyI18nString,
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                """Hello,

you bought a ticket for {event}.

If you did not do so already, you can download your ticket here:
{url}

Best regards,
Your {event} team"""
            )
        ),
    },
    'smtp_use_custom': {'default': 'False', 'type': bool},
    'smtp_host': {'default': '', 'type': str},
    'smtp_port': {'default': 587, 'type': int},
    'smtp_username': {'default': '', 'type': str},
    'smtp_password': {'default': '', 'type': str},
    'smtp_use_tls': {'default': 'True', 'type': bool},
    'smtp_use_ssl': {'default': 'False', 'type': bool},
    'primary_color': {
        'default': settings.PRETIX_PRIMARY_COLOR,
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'serializer_kwargs': dict(
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
        ),
        'form_kwargs': dict(
            label=_('Primary color'),
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
            widget=forms.TextInput(attrs={'class': 'colorpickerfield'}),
        ),
    },
    'theme_color_success': {
        'default': '#50a167',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'serializer_kwargs': dict(
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
        ),
        'form_kwargs': dict(
            label=_('Accent color for success'),
            help_text=_('We strongly suggest to use a shade of green.'),
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
            widget=forms.TextInput(attrs={'class': 'colorpickerfield'}),
        ),
    },
    'theme_color_danger': {
        'default': '#c44f4f',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'serializer_kwargs': dict(
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
        ),
        'form_kwargs': dict(
            label=_('Accent color for errors'),
            help_text=_('We strongly suggest to use a shade of red.'),
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
            widget=forms.TextInput(attrs={'class': 'colorpickerfield'}),
        ),
    },
    'theme_color_background': {
        'default': '#f5f5f5',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'serializer_kwargs': dict(
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
        ),
        'form_kwargs': dict(
            label=_('Page background color'),
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
            widget=forms.TextInput(attrs={'class': 'colorpickerfield no-contrast'}),
        ),
    },
    'hover_button_color': {
        'default': '#2185d0',
        'type': str,
        'form_class': forms.CharField,
        'serializer_class': serializers.CharField,
        'serializer_kwargs': dict(
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
        ),
        'form_kwargs': dict(
            label=_('Scroll-over color'),
            validators=[
                RegexValidator(
                    regex='^#[0-9a-fA-F]{6}$',
                    message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                ),
            ],
            widget=forms.TextInput(attrs={'class': 'colorpickerfield no-contrast'}),
        ),
    },
    'theme_round_borders': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Use round edges'),
        ),
    },
    'primary_font': {
        'default': 'Open Sans',
        'type': str,
        'form_class': forms.ChoiceField,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': lambda: dict(**primary_font_kwargs()),
        'form_kwargs': lambda: dict(
            label=_('Font'),
            help_text=_('Only respected by modern browsers.'),
            widget=FontSelect,
            **primary_font_kwargs(),
        ),
    },
    'presale_css_file': {'default': None, 'type': str},
    'presale_css_checksum': {'default': None, 'type': str},
    'presale_widget_css_file': {'default': None, 'type': str},
    'presale_widget_css_checksum': {'default': None, 'type': str},
    'logo_image': {
        'default': None,
        'type': File,
        'form_class': ExtFileField,
        'form_kwargs': dict(
            label=_('Header image'),
            ext_whitelist=('.png', '.jpg', '.gif', '.jpeg'),
            max_size=10 * 1024 * 1024,
            help_text=_(
                'If you provide a logo image, we will by default not show your event name and date '
                'in the page header. By default, we show your logo with a size of up to 1140x120 pixels. You '
                'can increase the size with the setting below. We recommend not using small details on the picture '
                'as it will be resized on smaller screens.'
            ),
        ),
        'serializer_class': UploadedFileField,
        'serializer_kwargs': dict(
            allowed_types=['image/png', 'image/jpeg', 'image/gif'],
            max_size=10 * 1024 * 1024,
        ),
    },
    'logo_image_large': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Use header image in its full size'),
            help_text=_('We recommend to upload a picture at least 1170 pixels wide.'),
        ),
    },
    'logo_show_title': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Show event title even if a header image is present'),
            help_text=_('The title will only be shown on the event front page.'),
        ),
    },
    'organizer_logo_image': {
        'default': None,
        'type': File,
        'form_class': ExtFileField,
        'form_kwargs': dict(
            label=_('Header image'),
            ext_whitelist=('.png', '.jpg', '.gif', '.jpeg'),
            max_size=10 * 1024 * 1024,
            help_text=_(
                'If you provide a logo image, we will by default not show your organization name '
                'in the page header. By default, we show your logo with a size of up to 1140x120 pixels. You '
                'can increase the size with the setting below. We recommend not using small details on the picture '
                'as it will be resized on smaller screens.'
            ),
        ),
        'serializer_class': UploadedFileField,
        'serializer_kwargs': dict(
            allowed_types=['image/png', 'image/jpeg', 'image/gif'],
            max_size=10 * 1024 * 1024,
        ),
    },
    'organizer_logo_image_large': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Use header image in its full size'),
            help_text=_('We recommend to upload a picture at least 1170 pixels wide.'),
        ),
    },
    'og_image': {
        'default': None,
        'type': File,
        'form_class': ExtFileField,
        'form_kwargs': dict(
            label=_('Social media image'),
            ext_whitelist=('.png', '.jpg', '.gif', '.jpeg'),
            max_size=10 * 1024 * 1024,
            help_text=_(
                'This picture will be used as a preview if you post links to your ticket shop on social media. '
                'Facebook advises to use a picture size of 1200 x 630 pixels, however some platforms like '
                'WhatsApp and Reddit only show a square preview, so we recommend to make sure it still looks good '
                'only the center square is shown. If you do not fill this, we will use the logo given above.'
            ),
        ),
        'serializer_class': UploadedFileField,
        'serializer_kwargs': dict(
            allowed_types=['image/png', 'image/jpeg', 'image/gif'],
            max_size=10 * 1024 * 1024,
        ),
    },
    'invoice_logo_image': {
        'default': None,
        'type': File,
        'form_class': ExtFileField,
        'form_kwargs': dict(
            label=_('Logo image'),
            ext_whitelist=('.png', '.jpg', '.gif', '.jpeg'),
            required=False,
            max_size=10 * 1024 * 1024,
            help_text=_('We will show your logo with a maximal height and width of 2.5 cm.'),
        ),
        'serializer_class': UploadedFileField,
        'serializer_kwargs': dict(
            allowed_types=['image/png', 'image/jpeg', 'image/gif'],
            max_size=10 * 1024 * 1024,
        ),
    },
    'frontpage_text': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(label=_('Frontpage text'), widget=I18nTextarea),
    },
    'event_info_text': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Info text'),
            widget=I18nTextarea,
            widget_kwargs={'attrs': {'rows': '2'}},
            help_text=_(
                'Not displayed anywhere by default, but if you want to, you can use this e.g. in ticket templates.'
            ),
        ),
    },
    'banner_text': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Banner text (top)'),
            widget=I18nTextarea,
            widget_kwargs={'attrs': {'rows': '2'}},
            help_text=_(
                'This text will be shown above every page of your shop. Please only use this for '
                'very important messages.'
            ),
        ),
    },
    'banner_text_bottom': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Banner text (bottom)'),
            widget=I18nTextarea,
            widget_kwargs={'attrs': {'rows': '2'}},
            help_text=_(
                'This text will be shown below every page of your shop. Please only use this for '
                'very important messages.'
            ),
        ),
    },
    'voucher_explanation_text': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Voucher explanation'),
            widget=I18nTextarea,
            widget_kwargs={'attrs': {'rows': '2'}},
            help_text=_(
                'This text will be shown next to the input for a voucher code. You can use it e.g. to explain '
                'how to obtain a voucher code.'
            ),
        ),
    },
    'attendee_data_explanation_text': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Attendee data explanation'),
            widget=I18nTextarea,
            widget_kwargs={'attrs': {'rows': '2'}},
            help_text=_(
                'This text will be shown above the questions asked for every admission product. You can use it e.g. '
                'to explain'
                'why you need information from them.'
            ),
        ),
    },
    'checkout_success_text': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Additional success message'),
            help_text=_(
                'This message will be shown after an order has been created successfully. It will be shown in '
                'additional'
                'to the default text.'
            ),
            widget_kwargs={'attrs': {'rows': '2'}},
            widget=I18nTextarea,
        ),
    },
    'checkout_phone_helptext': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Help text of the phone number field'),
            widget_kwargs={'attrs': {'rows': '2'}},
            widget=I18nTextarea,
        ),
    },
    'checkout_email_helptext': {
        'default': LazyI18nString.from_gettext(
            gettext_noop(
                'Make sure to enter a valid email address. We will send you an order '
                'confirmation including a link that you need to access your order later.'
            )
        ),
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Help text of the email field'),
            widget_kwargs={'attrs': {'rows': '2'}},
            widget=I18nTextarea,
        ),
    },
    'order_import_settings': {'default': '{}', 'type': dict},
    'organizer_info_text': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Info text'),
            widget=I18nTextarea,
            help_text=_(
                'Not displayed anywhere by default, but if you want to, you can use this e.g. in ticket templates.'
            ),
        ),
    },
    'event_team_provisioning': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Allow creating a new team during event creation'),
            help_text=_(
                'Users that do not have access to all events under this organizer, must select one of their teams '
                'to have access to the created event. This setting allows users to create an event-specified team'
                ' on-the-fly, even when they do not have "Can change teams and permissions" permission.'
            ),
        ),
    },
    'update_check_ack': {'default': 'False', 'type': bool},
    'update_check_email': {'default': '', 'type': str},
    # here is the default setting for the updates check
    'update_check_perform': {'default': 'False', 'type': bool},
    'update_check_result': {'default': None, 'type': dict},
    'update_check_result_warning': {'default': 'False', 'type': bool},
    'update_check_last': {'default': None, 'type': datetime},
    'update_check_id': {'default': None, 'type': str},
    'banner_message': {'default': '', 'type': LazyI18nString},
    'banner_message_detail': {'default': '', 'type': LazyI18nString},
    'opencagedata_apikey': {'default': None, 'type': str},
    'mapquest_apikey': {'default': None, 'type': str},
    'leaflet_tiles': {'default': None, 'type': str},
    'leaflet_tiles_attribution': {'default': None, 'type': str},
    'frontpage_subevent_ordering': {
        'default': 'date_ascending',
        'type': str,
        'serializer_class': serializers.ChoiceField,
        'serializer_kwargs': dict(
            choices=[
                ('date_ascending', _('Event start time')),
                ('date_descending', _('Event start time (descending)')),
                ('name_ascending', _('Name')),
                ('name_descending', _('Name (descending)')),
            ],
        ),
        'form_class': forms.ChoiceField,
        'form_kwargs': dict(
            label=pgettext('subevent', 'Date ordering'),
            choices=[
                ('date_ascending', _('Event start time')),
                ('date_descending', _('Event start time (descending)')),
                ('name_ascending', _('Name')),
                ('name_descending', _('Name (descending)')),
            ],
            # When adding a new ordering, remember to also define it in the event model
        ),
    },
    'organizer_link_back': {
        'default': 'False',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Link back to organizer overview on all event pages'),
        ),
    },
    'organizer_homepage_text': {
        'default': '',
        'type': LazyI18nString,
        'serializer_class': I18nField,
        'form_class': I18nFormField,
        'form_kwargs': dict(
            label=_('Homepage text'),
            widget=I18nTextarea,
            help_text=_('This will be displayed on the organizer homepage.'),
        ),
    },
    'name_scheme': {'default': 'full', 'type': str},
    'giftcard_length': {
        'default': settings.ENTROPY['giftcard_secret'],
        'type': int,
        'form_class': forms.IntegerField,
        'serializer_class': serializers.IntegerField,
        'form_kwargs': dict(
            label=_('Length of gift card codes'),
            help_text=_(
                'The system generates by default {}-character long gift card codes. However, if a different length '
                'is required, it can be set here.'.format(settings.ENTROPY['giftcard_secret'])
            ),
        ),
    },
    'giftcard_expiry_years': {
        'default': None,
        'type': int,
        'form_class': forms.IntegerField,
        'serializer_class': serializers.IntegerField,
        'form_kwargs': dict(
            label=_('Validity of gift card codes in years'),
            help_text=_(
                'If you set a number here, gift cards will by default expire at the end of the year after this '
                'many years. If you keep it empty, gift cards do not have an explicit expiry date.'
            ),
        ),
    },
    'privacy_policy': {
        'default': None,
        'type': LazyI18nString,
        'form_class': I18nURLFormField,
        'form_kwargs': dict(
            label=_('Privacy Policy URL'),
            help_text=_(
                'This should link to a section of your website that clearly '
                'explains how you collect, manage, and use the gathered data.'
            ),
            widget=I18nTextInput,
        ),
        'serializer_class': I18nURLField,
    },
    'seating_choice': {
        'default': 'True',
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Customers can choose their own seats'),
            help_text=_(
                'If disabled, you will need to manually assign seats in the backend. Note that this can mean '
                'people will not know their seat after their purchase and it might not be written on their '
                'ticket.'
            ),
        ),
        'type': bool,
    },
    'seating_minimal_distance': {'default': '0', 'type': float},
    'seating_allow_blocked_seats_for_channel': {'default': [], 'type': list},
    'seating_distance_within_row': {'default': 'False', 'type': bool},
    'checkout_show_copy_answers_button': {
        'default': 'True',
        'type': bool,
        'form_class': forms.BooleanField,
        'serializer_class': serializers.BooleanField,
        'form_kwargs': dict(
            label=_('Show button to copy user input from other products'),
        ),
    },
}

CSS_SETTINGS = {
    'primary_color',
    'theme_color_success',
    'theme_color_danger',
    'primary_font',
    'theme_color_background',
    'theme_round_borders',
    'hover_button_color',
}

TITLE_GROUP = OrderedDict(
    [
        (
            'english_common',
            (
                _('Most common English titles'),
                (
                    'Mr',
                    'Ms',
                    'Mrs',
                    'Miss',
                    'Mx',
                    'Dr',
                    'Professor',
                    'Sir',
                ),
            ),
        ),
        (
            'german_common',
            (
                _('Most common German titles'),
                (
                    'Dr.',
                    'Prof.',
                    'Prof. Dr.',
                ),
            ),
        ),
    ]
)

NAME_SALUTION = [
    pgettext_lazy('person_name_salutation', 'Ms'),
    pgettext_lazy('person_name_salutation', 'Mr'),
]

NAME_SCHEMES = OrderedDict(
    [
        (
            'given_family',
            {
                'fields': (
                    # field_name, label, weight for widget width
                    ('given_name', _('Given name'), 1),
                    ('family_name', _('Family name'), 1),
                ),
                'concatenation': lambda d: ' '.join(
                    str(p) for p in [d.get('given_name', ''), d.get('family_name', '')] if p
                ),
                'sample': {
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    '_scheme': 'given_family',
                },
            },
        ),
        (
            'title_given_family',
            {
                'fields': (
                    ('title', pgettext_lazy('person_name', 'Title'), 1),
                    ('given_name', _('Given name'), 2),
                    ('family_name', _('Family name'), 2),
                ),
                'concatenation': lambda d: ' '.join(
                    str(p)
                    for p in [
                        d.get('title', ''),
                        d.get('given_name', ''),
                        d.get('family_name', ''),
                    ]
                    if p
                ),
                'sample': {
                    'title': pgettext_lazy('person_name_sample', 'Dr'),
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    '_scheme': 'title_given_family',
                },
            },
        ),
        (
            'title_given_family',
            {
                'fields': (
                    ('title', pgettext_lazy('person_name', 'Title'), 1),
                    ('given_name', _('Given name'), 2),
                    ('family_name', _('Family name'), 2),
                ),
                'concatenation': lambda d: ' '.join(
                    str(p)
                    for p in [
                        d.get('title', ''),
                        d.get('given_name', ''),
                        d.get('family_name', ''),
                    ]
                    if p
                ),
                'sample': {
                    'title': pgettext_lazy('person_name_sample', 'Dr'),
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    '_scheme': 'title_given_family',
                },
            },
        ),
        (
            'given_middle_family',
            {
                'fields': (
                    ('given_name', _('First name'), 2),
                    ('middle_name', _('Middle name'), 1),
                    ('family_name', _('Family name'), 2),
                ),
                'concatenation': lambda d: ' '.join(
                    str(p)
                    for p in [
                        d.get('given_name', ''),
                        d.get('middle_name', ''),
                        d.get('family_name', ''),
                    ]
                    if p
                ),
                'sample': {
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'middle_name': 'M',
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    '_scheme': 'given_middle_family',
                },
            },
        ),
        (
            'title_given_middle_family',
            {
                'fields': (
                    ('title', pgettext_lazy('person_name', 'Title'), 1),
                    ('given_name', _('First name'), 2),
                    ('middle_name', _('Middle name'), 1),
                    ('family_name', _('Family name'), 1),
                ),
                'concatenation': lambda d: ' '.join(
                    str(p)
                    for p in [
                        d.get('title', ''),
                        d.get('given_name'),
                        d.get('middle_name'),
                        d.get('family_name'),
                    ]
                    if p
                ),
                'sample': {
                    'title': pgettext_lazy('person_name_sample', 'Dr'),
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'middle_name': 'M',
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    '_scheme': 'title_given_middle_family',
                },
            },
        ),
        (
            'family_given',
            {
                'fields': (
                    ('family_name', _('Family name'), 1),
                    ('given_name', _('Given name'), 1),
                ),
                'concatenation': lambda d: ' '.join(
                    str(p) for p in [d.get('family_name', ''), d.get('given_name', '')] if p
                ),
                'sample': {
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    '_scheme': 'family_given',
                },
            },
        ),
        (
            'family_nospace_given',
            {
                'fields': (
                    ('given_name', _('Given name'), 1),
                    ('family_name', _('Family name'), 1),
                ),
                'concatenation': lambda d: ''.join(
                    str(p) for p in [d.get('family_name', ''), d.get('given_name', '')] if p
                ),
                'sample': {
                    'given_name': '泽东',
                    'family_name': '毛',
                    '_scheme': 'family_nospace_given',
                },
            },
        ),
        (
            'family_comma_given',
            {
                'fields': (
                    ('given_name', _('Given name'), 1),
                    ('family_name', _('Family name'), 1),
                ),
                'concatenation': lambda d: (
                    str(d.get('family_name', ''))
                    + str((', ' if d.get('family_name') and d.get('given_name') else ''))
                    + str(d.get('given_name', ''))
                ),
                'sample': {
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    '_scheme': 'family_comma_given',
                },
            },
        ),
        (
            'full',
            {
                'fields': (('full_name', _('Name'), 1),),
                'concatenation': lambda d: str(d.get('full_name', '')),
                'sample': {
                    'full_name': pgettext_lazy('person_name_sample', 'John Doe'),
                    '_scheme': 'full',
                },
            },
        ),
        (
            'calling_full',
            {
                'fields': (
                    ('calling_name', _('Calling name'), 1),
                    ('full_name', _('Full name'), 2),
                ),
                'concatenation': lambda d: str(d.get('full_name', '')),
                'sample': {
                    'full_name': pgettext_lazy('person_name_sample', 'John Doe'),
                    'calling_name': pgettext_lazy('person_name_sample', 'John'),
                    '_scheme': 'calling_full',
                },
            },
        ),
        (
            'full_transcription',
            {
                'fields': (
                    ('full_name', _('Full name'), 1),
                    ('latin_transcription', _('Latin transcription'), 2),
                ),
                'concatenation': lambda d: str(d.get('full_name', '')),
                'sample': {
                    'full_name': '庄司',
                    'latin_transcription': 'Shōji',
                    '_scheme': 'full_transcription',
                },
            },
        ),
        (
            'salutation_given_family',
            {
                'fields': (
                    ('salutation', pgettext_lazy('person_name', 'Salutation'), 1),
                    ('given_name', _('Given name'), 2),
                    ('family_name', _('Family name'), 2),
                ),
                'concatenation': lambda d: ' '.join(
                    str(p) for p in (d.get(key, '') for key in ['given_name', 'family_name']) if p
                ),
                'sample': {
                    'salutation': pgettext_lazy('person_name_sample', 'Mr'),
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    '_scheme': 'salutation_given_family',
                },
            },
        ),
        (
            'salutation_title_given_family',
            {
                'fields': (
                    ('salutation', pgettext_lazy('person_name', 'Salutation'), 1),
                    ('title', pgettext_lazy('person_name', 'Title'), 1),
                    ('given_name', _('Given name'), 2),
                    ('family_name', _('Family name'), 2),
                ),
                'concatenation': lambda d: ' '.join(
                    str(p) for p in (d.get(key, '') for key in ['title', 'given_name', 'family_name']) if p
                ),
                'sample': {
                    'salutation': pgettext_lazy('person_name_sample', 'Mr'),
                    'title': pgettext_lazy('person_name_sample', 'Dr'),
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    '_scheme': 'salutation_title_given_family',
                },
            },
        ),
        (
            'salutation_title_given_family_degree',
            {
                'fields': (
                    ('salutation', pgettext_lazy('person_name', 'Salutation'), 1),
                    ('title', pgettext_lazy('person_name', 'Title'), 1),
                    ('given_name', _('Given name'), 2),
                    ('family_name', _('Family name'), 2),
                    ('degree', pgettext_lazy('person_name', 'Degree (after name)'), 2),
                ),
                'concatenation': lambda d: (
                    ' '.join(str(p) for p in (d.get(key, '') for key in ['title', 'given_name', 'family_name']) if p)
                    + str((', ' if d.get('degree') else ''))
                    + str(d.get('degree', ''))
                ),
                'sample': {
                    'salutation': pgettext_lazy('person_name_sample', 'Mr'),
                    'title': pgettext_lazy('person_name_sample', 'Dr'),
                    'given_name': pgettext_lazy('person_name_sample', 'John'),
                    'family_name': pgettext_lazy('person_name_sample', 'Doe'),
                    'degree': pgettext_lazy('person_name_sample', 'MA'),
                    '_scheme': 'salutation_title_given_family_degree',
                },
            },
        ),
    ]
)

COUNTRIES_WITH_STATE = {
    # Source: http://www.bitboost.com/ref/international-address-formats.html
    # This is not a list of countries that *have* states, this is a list of countries where states
    # are actually *used* in postal addresses. This is obviously not complete and opinionated.
    # Country: [(List of subdivision types as defined by pycountry), (short or long form to be used)]
    'AU': (['State', 'Territory'], 'short'),
    'BR': (['State'], 'short'),
    'CA': (['Province', 'Territory'], 'short'),
    # 'CN': (['Province', 'Autonomous region', 'Munincipality'], 'long'),
    'MY': (['State'], 'long'),
    'MX': (['State', 'Federal District'], 'short'),
    'US': (['State', 'Outlying area', 'District'], 'short'),
}
