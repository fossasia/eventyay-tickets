from decimal import Decimal

from eventyay.base.decimal import round_decimal
from eventyay.base.models import (
    AbstractPosition,
    InvoiceAddress,
    Product,
    ProductAddOn,
    ProductVariation,
    Voucher,
)
from eventyay.base.models.event import SubEvent
from eventyay.base.models.tax import TAXED_ZERO, TaxedPrice, TaxRule


def get_price(
    product: Product,
    variation: ProductVariation = None,
    voucher: Voucher = None,
    custom_price: Decimal = None,
    subevent: SubEvent = None,
    custom_price_is_net: bool = False,
    custom_price_is_tax_rate: Decimal = None,
    addon_to: AbstractPosition = None,
    invoice_address: InvoiceAddress = None,
    force_custom_price: bool = False,
    bundled_sum: Decimal = Decimal('0.00'),
    max_discount: Decimal = None,
    tax_rule=None,
) -> TaxedPrice:
    if addon_to:
        try:
            iao = addon_to.product.addons.get(addon_category_id=product.category_id)
            if iao.price_included:
                return TAXED_ZERO
        except ProductAddOn.DoesNotExist:
            pass

    price = product.default_price
    if subevent and product.pk in subevent.product_price_overrides:
        price = subevent.product_price_overrides[product.pk]

    if variation is not None:
        if variation.default_price is not None:
            price = variation.default_price
        if subevent and variation.pk in subevent.var_price_overrides:
            price = subevent.var_price_overrides[variation.pk]

    if voucher:
        price = voucher.calculate_price(price, max_discount=max_discount)

    if tax_rule is not None:
        tax_rule = tax_rule
    elif product.tax_rule:
        tax_rule = product.tax_rule
    else:
        tax_rule = TaxRule(
            name='',
            rate=Decimal('0.00'),
            price_includes_tax=True,
            eu_reverse_charge=False,
        )

    if force_custom_price and custom_price is not None and custom_price != '':
        if custom_price_is_net:
            price = tax_rule.tax(
                custom_price,
                base_price_is='net',
                invoice_address=invoice_address,
                subtract_from_gross=bundled_sum,
            )
        else:
            price = tax_rule.tax(
                custom_price,
                base_price_is='gross',
                invoice_address=invoice_address,
                subtract_from_gross=bundled_sum,
            )
    elif product.free_price and custom_price is not None and custom_price != '':
        if not isinstance(custom_price, Decimal):
            custom_price = Decimal(str(custom_price).replace(',', '.'))
        if custom_price > 100000000:
            raise ValueError('price_too_high')

        price = tax_rule.tax(price, invoice_address=invoice_address)

        if custom_price_is_net:
            price = tax_rule.tax(
                max(custom_price, price.net),
                base_price_is='net',
                invoice_address=invoice_address,
                subtract_from_gross=bundled_sum,
            )
        else:
            price = tax_rule.tax(
                max(custom_price, price.gross),
                base_price_is='gross',
                gross_price_is_tax_rate=custom_price_is_tax_rate,
                invoice_address=invoice_address,
                subtract_from_gross=bundled_sum,
            )
    else:
        price = tax_rule.tax(price, invoice_address=invoice_address, subtract_from_gross=bundled_sum)

    price.gross = round_decimal(price.gross, product.event.currency)
    price.net = round_decimal(price.net, product.event.currency)
    price.tax = price.gross - price.net

    return price
