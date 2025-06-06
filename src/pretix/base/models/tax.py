import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.formats import localize
from django.utils.timezone import get_current_timezone, now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext
from i18nfield.fields import I18nCharField
from i18nfield.strings import LazyI18nString

from pretix.base.decimal import round_decimal
from pretix.base.models.base import LoggedModel
from pretix.base.templatetags.money import money_filter
from pretix.helpers.countries import FastCountryField


class TaxedPrice:
    def __init__(self, *, gross: Decimal, net: Decimal, tax: Decimal, rate: Decimal, name: str):
        if net + tax != gross:
            raise ValueError('Net value and tax value need to add to the gross value')
        self.gross = gross
        self.net = net
        self.tax = tax
        self.rate = rate
        self.name = name

    def __repr__(self):
        return '{} + {}% = {}'.format(localize(self.net), localize(self.rate), localize(self.gross))

    def print(self, currency):
        return '{} + {}% = {}'.format(
            money_filter(self.net, currency),
            localize(self.rate),
            money_filter(self.gross, currency),
        )

    def __sub__(self, other):
        newgross = self.gross - other.gross
        newnet = round_decimal(newgross - (newgross * (1 - 100 / (100 + self.rate)))).quantize(
            Decimal('10') ** self.gross.as_tuple().exponent
        )
        return TaxedPrice(
            gross=newgross,
            net=newnet,
            tax=newgross - newnet,
            rate=self.rate,
            name=self.name,
        )

    def __mul__(self, other):
        newgross = self.gross * other
        newnet = round_decimal(newgross - (newgross * (1 - 100 / (100 + self.rate)))).quantize(
            Decimal('10') ** self.gross.as_tuple().exponent
        )
        return TaxedPrice(
            gross=newgross,
            net=newnet,
            tax=newgross - newnet,
            rate=self.rate,
            name=self.name,
        )


TAXED_ZERO = TaxedPrice(
    gross=Decimal('0.00'),
    net=Decimal('0.00'),
    tax=Decimal('0.00'),
    rate=Decimal('0.00'),
    name='',
)

EU_COUNTRIES = {
    'AT',
    'BE',
    'BG',
    'HR',
    'CY',
    'CZ',
    'DK',
    'EE',
    'FI',
    'FR',
    'DE',
    'GR',
    'HU',
    'IE',
    'IT',
    'LV',
    'LT',
    'LU',
    'MT',
    'NL',
    'PL',
    'PT',
    'RO',
    'SK',
    'SI',
    'ES',
    'SE',
    'GB',
}
EU_CURRENCIES = {
    'BG': 'BGN',
    'GB': 'GBP',
    'HR': 'HRK',
    'CZ': 'CZK',
    'DK': 'DKK',
    'HU': 'HUF',
    'PL': 'PLN',
    'RO': 'RON',
    'SE': 'SEK',
}


def is_eu_country(cc):
    cc = str(cc)
    if cc == 'GB':
        return now().astimezone(get_current_timezone()).year <= 2020
    else:
        return cc in EU_COUNTRIES


def cc_to_vat_prefix(country_code):
    if country_code == 'GR':
        return 'EL'
    return country_code


class TaxRule(LoggedModel):
    event = models.ForeignKey('Event', related_name='tax_rules', on_delete=models.CASCADE)
    name = I18nCharField(
        verbose_name=_('Name'),
        help_text=_('Should be short, e.g. "VAT"'),
        max_length=190,
    )
    rate = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Tax rate'))
    price_includes_tax = models.BooleanField(
        verbose_name=_('The configured product prices include the tax amount'),
        default=True,
    )
    eu_reverse_charge = models.BooleanField(
        verbose_name=_('Use EU reverse charge taxation rules'),
        default=False,
        help_text=_(
            'Not recommended. Most events will NOT be qualified for reverse charge since the place of '
            'taxation is the location of the event. This option disables charging VAT for all customers '
            'outside the EU and for business customers in different EU countries who entered a valid EU VAT '
            'ID. Only enable this option after consulting a tax counsel. No warranty given for correct tax '
            'calculation. USE AT YOUR OWN RISK.'
        ),
    )
    home_country = FastCountryField(
        verbose_name=_('Merchant country'),
        blank=True,
        help_text=_(
            'Your country of residence. This is the country the EU reverse charge rule will not apply in, '
            'if configured above.'
        ),
    )
    custom_rules = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('event', 'rate', 'id')

    class SaleNotAllowed(Exception):  # NOQA: N818
        pass

    def allow_delete(self):
        from pretix.base.models.orders import OrderFee, OrderPosition

        return (
            not OrderFee.objects.filter(tax_rule=self, order__event=self.event).exists()
            and not OrderPosition.all.filter(tax_rule=self, order__event=self.event).exists()
            and not self.event.items.filter(tax_rule=self).exists()
            and self.event.settings.tax_rate_default != self
        )

    @classmethod
    def zero(cls):
        return cls(
            event=None,
            name='',
            rate=Decimal('0.00'),
            price_includes_tax=True,
            eu_reverse_charge=False,
        )

    def clean(self):
        if self.eu_reverse_charge and not self.home_country:
            raise ValidationError(_('You need to set your home country to use the reverse charge feature.'))

    def __str__(self):
        if self.price_includes_tax:
            s = _('incl. {rate}% {name}').format(rate=self.rate, name=self.name)
        else:
            s = _('plus {rate}% {name}').format(rate=self.rate, name=self.name)
        if self.eu_reverse_charge:
            s += ' ({})'.format(_('reverse charge enabled'))
        return str(s)

    @property
    def has_custom_rules(self):
        return self.custom_rules and self.custom_rules != '[]'

    def tax_rate_for(self, invoice_address):
        if not self._tax_applicable(invoice_address):
            return Decimal('0.00')
        if self.has_custom_rules:
            rule = self.get_matching_rule(invoice_address)
            if rule.get('action', 'vat') == 'block':
                raise self.SaleNotAllowed()
            if rule.get('action', 'vat') == 'vat' and rule.get('rate') is not None:
                return Decimal(rule.get('rate'))
        return Decimal(self.rate)

    def tax(
        self,
        base_price,
        base_price_is='auto',
        currency=None,
        override_tax_rate=None,
        invoice_address=None,
        subtract_from_gross=Decimal('0.00'),
        gross_price_is_tax_rate: Decimal = None,
        force_fixed_gross_price=False,
    ):
        from .event import Event

        try:
            currency = currency or self.event.currency
        except Event.DoesNotExist:
            pass

        rate = Decimal(self.rate)
        if override_tax_rate is not None:
            rate = override_tax_rate
        elif invoice_address:
            adjust_rate = self.tax_rate_for(invoice_address)
            if (adjust_rate == gross_price_is_tax_rate or force_fixed_gross_price) and base_price_is == 'gross':
                rate = adjust_rate
            elif adjust_rate != rate:
                normal_price = self.tax(
                    base_price,
                    base_price_is,
                    currency,
                    subtract_from_gross=subtract_from_gross,
                )
                base_price = normal_price.net
                base_price_is = 'net'
                subtract_from_gross = Decimal('0.00')
                rate = adjust_rate

        if rate == Decimal('0.00'):
            return TaxedPrice(
                net=base_price - subtract_from_gross,
                gross=base_price - subtract_from_gross,
                tax=Decimal('0.00'),
                rate=rate,
                name=self.name,
            )

        if base_price_is == 'auto':
            if self.price_includes_tax:
                base_price_is = 'gross'
            else:
                base_price_is = 'net'

        if base_price_is == 'gross':
            if base_price >= Decimal('0.00'):
                # For positive prices, make sure they don't go negative because of bundles
                gross = max(Decimal('0.00'), base_price - subtract_from_gross)
            else:
                # If the price is already negative, we don't really care any more
                gross = base_price - subtract_from_gross
            net = round_decimal(gross - (gross * (1 - 100 / (100 + rate))), currency)
        elif base_price_is == 'net':
            net = base_price
            gross = round_decimal((net * (1 + rate / 100)), currency)
            if subtract_from_gross:
                gross -= subtract_from_gross
                net = round_decimal(gross - (gross * (1 - 100 / (100 + rate))), currency)
        else:
            raise ValueError('Unknown base price type: {}'.format(base_price_is))

        return TaxedPrice(net=net, gross=gross, tax=gross - net, rate=rate, name=self.name)

    @property
    def _custom_rules(self):
        if not self.custom_rules:
            return []
        return json.loads(self.custom_rules)

    def get_matching_rule(self, invoice_address):
        rules = self._custom_rules
        if invoice_address:
            for r in rules:
                if r['country'] == 'EU' and not is_eu_country(invoice_address.country):
                    continue
                if r['country'] not in ('ZZ', 'EU') and r['country'] != str(invoice_address.country):
                    continue
                if r['address_type'] == 'individual' and invoice_address.is_business:
                    continue
                if r['address_type'] in ('business', 'business_vat_id') and not invoice_address.is_business:
                    continue
                if r['address_type'] == 'business_vat_id' and (
                    not invoice_address.vat_id or not invoice_address.vat_id_validated
                ):
                    continue
                return r
        return {'action': 'vat'}

    def invoice_text(self, invoice_address):
        if self._custom_rules:
            rule = self.get_matching_rule(invoice_address)
            t = rule.get('invoice_text', {})
            if t and any(l for l in t.values()):
                return str(LazyI18nString(t))
        if self.is_reverse_charge(invoice_address):
            if is_eu_country(invoice_address.country):
                return pgettext(
                    'invoice',
                    'Reverse Charge: According to Article 194, 196 of Council Directive 2006/112/EEC, VAT liability '
                    'rests with the service recipient.',
                )
            else:
                return pgettext('invoice', 'VAT liability rests with the service recipient.')

    def is_reverse_charge(self, invoice_address):
        if self._custom_rules:
            rule = self.get_matching_rule(invoice_address)
            return rule['action'] == 'reverse'

        if not self.eu_reverse_charge:
            return False

        if not invoice_address or not invoice_address.country:
            return False

        if not is_eu_country(invoice_address.country):
            return False

        if invoice_address.country == self.home_country:
            return False

        if invoice_address.is_business and invoice_address.vat_id and invoice_address.vat_id_validated:
            return True

        return False

    def _tax_applicable(self, invoice_address):
        if self._custom_rules:
            rule = self.get_matching_rule(invoice_address)
            if rule.get('action', 'vat') == 'block':
                raise self.SaleNotAllowed()
            return rule.get('action', 'vat') == 'vat'

        if not self.eu_reverse_charge:
            # No reverse charge rules? Always apply VAT!
            return True

        if not invoice_address or not invoice_address.country:
            # No country specified? Always apply VAT!
            return True

        if not is_eu_country(invoice_address.country):
            # Non-EU country? Never apply VAT!
            return False

        if invoice_address.country == self.home_country:
            # Within same EU country? Always apply VAT!
            return True

        if invoice_address.is_business and invoice_address.vat_id and invoice_address.vat_id_validated:
            # Reverse charge case
            return False

        # Consumer in different EU country / invalid VAT
        return True

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        if self.event:
            self.event.cache.clear()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.event:
            self.event.cache.clear()
