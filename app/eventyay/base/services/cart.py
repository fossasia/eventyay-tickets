from collections import Counter, defaultdict, namedtuple
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import List, Optional

from celery.exceptions import MaxRetriesExceededError
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Value
from django.dispatch import receiver
from django.utils.timezone import make_aware, now
from django.utils.translation import gettext as _
from django.utils.translation import pgettext_lazy
from django_scopes import scopes_disabled

from eventyay.base.channels import get_all_sales_channels
from eventyay.base.configurations.lazy_i18n_string_list_base import (
    LazyI18nStringList,
)
from eventyay.base.i18n import language
from eventyay.base.models import (
    CartPosition,
    Event,
    InvoiceAddress,
    Order,
    Product,
    ProductVariation,
    Seat,
    SeatCategoryMapping,
    Voucher,
)
from eventyay.base.models.event import SubEvent
from eventyay.base.models.orders import OrderFee, OrderPosition
from eventyay.base.models.product import ProductMetaValue
from eventyay.base.models.tax import TAXED_ZERO, TaxedPrice, TaxRule
from eventyay.base.reldate import RelativeDateWrapper
from eventyay.base.services.checkin import _save_answers
from eventyay.base.services.locking import LockTimeoutException, NoLockManager
from eventyay.base.services.pricing import get_price
from eventyay.base.services.quotas import QuotaAvailability
from eventyay.base.services.tasks import ProfiledEventTask
from eventyay.base.settings import PERSON_NAME_SCHEMES
from eventyay.base.signals import validate_cart_addons
from eventyay.base.templatetags.rich_text import rich_text
from eventyay.celery_app import app
from eventyay.presale.signals import (
    checkout_confirm_messages,
    fee_calculation_for_cart,
)


class CartError(Exception):
    def __init__(self, *args):
        msg = args[0]
        msgargs = args[1] if len(args) > 1 else None
        self.args = args
        if msgargs:
            msg = _(msg) % msgargs
        else:
            msg = _(msg)
        super().__init__(msg)


error_messages = {
    'busy': _('We were not able to process your request completely as the server was too busy. Please try again.'),
    'empty': _('You did not select any products.'),
    'unknown_position': _('Unknown cart position.'),
    'subevent_required': pgettext_lazy('subevent', 'No date was specified.'),
    'not_for_sale': _('You selected a product which is not available for sale.'),
    'unavailable': _('Some of the products you selected are no longer available. Please see below for details.'),
    'in_part': _(
        'Some of the products you selected are no longer available in '
        'the quantity you selected. Please see below for details.'
    ),
    'max_products': _('You cannot select more than %s products per order.'),
    'max_products_per_product': _('You cannot select more than %(max)s products of the product %(product)s.'),
    'min_products_per_product': _('You need to select at least %(min)s products of the product %(product)s.'),
    'min_products_per_product_removed': _(
        'We removed %(product)s from your cart as you can not buy less than %(min)s items of it.'
    ),
    'not_started': _('The presale period for this event has not yet started.'),
    'ended': _('The presale period for this event has ended.'),
    'payment_ended': _('All payments for this event need to be confirmed already, so no new orders can be created.'),
    'some_subevent_not_started': _(
        'The presale period for this event has not yet started. The affected positions '
        'have been removed from your cart.'
    ),
    'some_subevent_ended': _(
        'The presale period for one of the events in your cart has ended. The affected '
        'positions have been removed from your cart.'
    ),
    'price_too_high': _('The entered price is to high.'),
    'voucher_invalid': _('This voucher code is not known in our database.'),
    'voucher_redeemed': _('This voucher code has already been used the maximum number of times allowed.'),
    'voucher_redeemed_cart': _(
        'This voucher code is currently locked since it is already contained in a cart. This '
        'might mean that someone else is redeeming this voucher right now, or that you tried '
        'to redeem it before but did not complete the checkout process. You can try to use it '
        'again in %d minutes.'
    ),
    'voucher_redeemed_partial': _('This voucher code can only be redeemed %d more times.'),
    'voucher_double': _(
        'You already used this voucher code. Remove the associated line from your '
        'cart if you want to use it for a different product.'
    ),
    'voucher_expired': _('This voucher is expired.'),
    'voucher_invalid_product': _('This voucher is not valid for this product.'),
    'voucher_invalid_seat': _('This voucher is not valid for this seat.'),
    'voucher_no_match': _(
        'We did not find any position in your cart that we could use this voucher for. If you want '
        'to add something new to your cart using that voucher, you can do so with the voucher '
        'redemption option on the bottom of the page.'
    ),
    'voucher_product_not_available': _('Your voucher is valid for a product that is currently not for sale.'),
    'voucher_invalid_subevent': pgettext_lazy('subevent', 'This voucher is not valid for this event date.'),
    'voucher_required': _('You need a valid voucher code to order this product.'),
    'inactive_subevent': pgettext_lazy('subevent', 'The selected event date is not active.'),
    'addon_invalid_base': _('You can not select an add-on for the selected product.'),
    'addon_duplicate_product': _('You can not select two variations of the same add-on product.'),
    'addon_max_count': _('You can select at most %(max)s add-ons from the category %(cat)s for the product %(base)s.'),
    'addon_min_count': _(
        'You need to select at least %(min)s add-ons from the category %(cat)s for the product %(base)s.'
    ),
    'addon_no_multi': _(
        'You can select every add-ons from the category %(cat)s for the product %(base)s at most once.'
    ),
    'addon_only': _('One of the products you selected can only be bought as an add-on to another project.'),
    'bundled_only': _('One of the products you selected can only be bought part of a bundle.'),
    'seat_required': _('You need to select a specific seat.'),
    'seat_invalid': _('Please select a valid seat.'),
    'seat_forbidden': _('You can not select a seat for this position.'),
    'seat_unavailable': _('The seat you selected has already been taken. Please select a different seat.'),
    'seat_multiple': _('You can not select the same seat multiple times.'),
    'gift_card': _(
        'You entered a gift card instead of a voucher. '
        "Gift cards can be entered later on when you're asked for your payment details."
    ),
    'country_blocked': _('One of the selected products is not available in the selected country.'),
    'one_ticket_per_user': _('Only one ticket per user is allowed for a product in your cart. You already have a ticket.'),
    'one_ticket_per_user_cart': _('Only one ticket per user is allowed for this product. Quantity has been adjusted to 1.'),
}


class CartManager:
    AddOperation = namedtuple(
        'AddOperation',
        (
            'count',
            'product',
            'variation',
            'price',
            'voucher',
            'quotas',
            'addon_to',
            'subevent',
            'includes_tax',
            'bundled',
            'seat',
            'price_before_voucher',
        ),
    )
    RemoveOperation = namedtuple('RemoveOperation', ('position',))
    VoucherOperation = namedtuple('VoucherOperation', ('position', 'voucher', 'price'))
    ExtendOperation = namedtuple(
        'ExtendOperation',
        (
            'position',
            'count',
            'product',
            'variation',
            'price',
            'voucher',
            'quotas',
            'subevent',
            'seat',
            'price_before_voucher',
        ),
    )
    order = {
        RemoveOperation: 10,
        VoucherOperation: 15,
        ExtendOperation: 20,
        AddOperation: 30,
    }

    def __init__(
        self,
        event: Event,
        cart_id: str,
        invoice_address: InvoiceAddress = None,
        widget_data=None,
        sales_channel='web',
    ):
        self.event = event
        self.cart_id = cart_id
        self.now_dt = now()
        self._operations = []
        self._quota_diff = Counter()
        self._voucher_use_diff = Counter()
        self._products_cache = {}
        self._subevents_cache = {}
        self._variations_cache = {}
        self._seated_cache = {}
        self._expiry = None
        self.invoice_address = invoice_address
        self._widget_data = widget_data or {}
        self._sales_channel = sales_channel
        self._last_warning = None

    def get_last_warning(self):
        """Get the last warning message from cart operations."""
        return self._last_warning

    @property
    def positions(self):
        return CartPosition.objects.filter(Q(cart_id=self.cart_id) & Q(event=self.event)).select_related(
            'product', 'subevent'
        )

    def _is_seated(self, product, subevent):
        if not self.event.settings.seating_choice:
            return False
        if (product, subevent) not in self._seated_cache:
            self._seated_cache[product, subevent] = product.seat_category_mappings.filter(subevent=subevent).exists()
        return self._seated_cache[product, subevent]

    def _calculate_expiry(self):
        self._expiry = self.now_dt + timedelta(minutes=self.event.settings.get('reservation_time', as_type=int))

    def _check_presale_dates(self):
        if self.event.presale_start and self.now_dt < self.event.presale_start:
            raise CartError(error_messages['not_started'])
        if self.event.presale_has_ended:
            raise CartError(error_messages['ended'])
        if not self.event.has_subevents:
            tlv = self.event.settings.get('payment_term_last', as_type=RelativeDateWrapper)
            if tlv:
                term_last = make_aware(
                    datetime.combine(
                        tlv.datetime(self.event).date(),
                        time(hour=23, minute=59, second=59),
                    ),
                    self.event.timezone,
                )
                if term_last < self.now_dt:
                    raise CartError(error_messages['payment_ended'])

    def _extend_expiry_of_valid_existing_positions(self):
        # Extend this user's cart session to ensure all products in the cart expire at the same time
        # We can extend the reservation of products which are not yet expired without risk
        self.positions.filter(expires__gt=self.now_dt).update(expires=self._expiry)

    def _delete_out_of_timeframe(self):
        err = None
        for cp in self.positions:
            if cp.subevent and cp.subevent.presale_start and self.now_dt < cp.subevent.presale_start:
                err = error_messages['some_subevent_not_started']
                cp.addons.all().delete()
                cp.delete()

            if cp.subevent and cp.subevent.presale_end and self.now_dt > cp.subevent.presale_end:
                err = error_messages['some_subevent_ended']
                cp.addons.all().delete()
                cp.delete()

            if cp.subevent:
                tlv = self.event.settings.get('payment_term_last', as_type=RelativeDateWrapper)
                if tlv:
                    term_last = make_aware(
                        datetime.combine(
                            tlv.datetime(cp.subevent).date(),
                            time(hour=23, minute=59, second=59),
                        ),
                        self.event.timezone,
                    )
                    if term_last < self.now_dt:
                        err = error_messages['some_subevent_ended']
                        cp.addons.all().delete()
                        cp.delete()
        return err

    def _update_subevents_cache(self, se_ids: List[int]):
        self._subevents_cache.update(
            {
                i.pk: i
                for i in self.event.subevents.filter(id__in=[i for i in se_ids if i and i not in self._subevents_cache])
            }
        )

    def _update_products_cache(self, product_ids: List[int], variation_ids: List[int]):
        self._products_cache.update(
            {
                i.pk: i
                for i in self.event.products.select_related('category')
                .prefetch_related('addons', 'bundles', 'addons__addon_category', 'quotas')
                .annotate(
                    has_variations=Count('variations'),
                )
                .filter(id__in=[i for i in product_ids if i and i not in self._products_cache])
                .order_by()
            }
        )
        self._variations_cache.update(
            {
                v.pk: v
                for v in ProductVariation.objects.filter(product__event=self.event)
                .prefetch_related('quotas')
                .select_related('product', 'product__event')
                .filter(id__in=[i for i in variation_ids if i and i not in self._variations_cache])
                .order_by()
            }
        )

    def _check_max_cart_size(self):
        if not get_all_sales_channels()[self._sales_channel].unlimited_products_per_order:
            cartsize = self.positions.filter(addon_to__isnull=True).count()
            cartsize += sum(
                [op.count for op in self._operations if isinstance(op, self.AddOperation) and not op.addon_to]
            )
            cartsize -= len(
                [1 for op in self._operations if isinstance(op, self.RemoveOperation) if not op.position.addon_to_id]
            )
            if cartsize > int(self.event.settings.max_products_per_order):
                # TODO: i18n plurals
                raise CartError(_(error_messages['max_products']) % (self.event.settings.max_products_per_order,))

    def _check_product_constraints(self, op, current_ops=[]):
        if isinstance(op, (self.AddOperation, self.ExtendOperation)):
            if not (
                (isinstance(op, self.AddOperation) and op.addon_to == 'FAKE')
                or (isinstance(op, self.ExtendOperation) and op.position.is_bundled)
            ):
                if op.product.require_voucher and op.voucher is None:
                    raise CartError(error_messages['voucher_required'])

                if op.product.hide_without_voucher and (op.voucher is None or not op.voucher.show_hidden_products):
                    raise CartError(error_messages['voucher_required'])

            if not op.product.is_available() or (op.variation and not op.variation.active):
                raise CartError(error_messages['unavailable'])

            if self._sales_channel not in op.product.sales_channels:
                raise CartError(error_messages['unavailable'])

            if (
                op.subevent
                and op.product.pk in op.subevent.product_overrides
                and op.subevent.product_overrides[op.product.pk].disabled
            ):
                raise CartError(error_messages['not_for_sale'])

            if (
                op.subevent
                and op.variation
                and op.variation.pk in op.subevent.var_overrides
                and op.subevent.var_overrides[op.variation.pk].disabled
            ):
                raise CartError(error_messages['not_for_sale'])

            if op.product.has_variations and not op.variation:
                raise CartError(error_messages['not_for_sale'])

            if op.variation and op.variation.product_id != op.product.pk:
                raise CartError(error_messages['not_for_sale'])

            if op.voucher and not op.voucher.applies_to(op.product, op.variation):
                raise CartError(error_messages['voucher_invalid_product'])

            if op.voucher and op.voucher.seat and op.voucher.seat != op.seat:
                raise CartError(error_messages['voucher_invalid_seat'])

            if op.voucher and op.voucher.subevent_id and op.voucher.subevent_id != op.subevent.pk:
                raise CartError(error_messages['voucher_invalid_subevent'])

            if op.subevent and not op.subevent.active:
                raise CartError(error_messages['inactive_subevent'])

            if op.subevent and op.subevent.presale_start and self.now_dt < op.subevent.presale_start:
                raise CartError(error_messages['not_started'])

            if op.subevent and op.subevent.presale_has_ended:
                raise CartError(error_messages['ended'])

            seated = self._is_seated(op.product, op.subevent)
            if seated and (
                not op.seat
                or (
                    op.seat.blocked
                    and self._sales_channel not in self.event.settings.seating_allow_blocked_seats_for_channel
                )
            ):
                raise CartError(error_messages['seat_invalid'])
            elif op.seat and not seated:
                raise CartError(error_messages['seat_forbidden'])
            elif op.seat and op.seat.product != op.product:
                raise CartError(error_messages['seat_invalid'])
            elif op.seat and op.count > 1:
                raise CartError('Invalid request: A seat can only be bought once.')

            if op.subevent:
                tlv = self.event.settings.get('payment_term_last', as_type=RelativeDateWrapper)
                if tlv:
                    term_last = make_aware(
                        datetime.combine(
                            tlv.datetime(op.subevent).date(),
                            time(hour=23, minute=59, second=59),
                        ),
                        self.event.timezone,
                    )
                    if term_last < self.now_dt:
                        raise CartError(error_messages['payment_ended'])

        if isinstance(op, self.AddOperation):
            if op.product.category and op.product.category.is_addon and not (op.addon_to and op.addon_to != 'FAKE'):
                raise CartError(error_messages['addon_only'])

            if op.product.require_bundling and not op.addon_to == 'FAKE':
                raise CartError(error_messages['bundled_only'])

    def _get_price(
        self,
        product: Product,
        variation: Optional[ProductVariation],
        voucher: Optional[Voucher],
        custom_price: Optional[Decimal],
        subevent: Optional[SubEvent],
        cp_is_net: bool = None,
        force_custom_price=False,
        bundled_sum=Decimal('0.00'),
    ):
        try:
            return get_price(
                product,
                variation,
                voucher,
                custom_price,
                subevent,
                custom_price_is_net=cp_is_net if cp_is_net is not None else self.event.settings.display_net_prices,
                invoice_address=self.invoice_address,
                force_custom_price=force_custom_price,
                bundled_sum=bundled_sum,
            )
        except TaxRule.SaleNotAllowed:
            raise CartError(error_messages['country_blocked'])
        except ValueError as e:
            if str(e) == 'price_too_high':
                raise CartError(error_messages['price_too_high'])
            else:
                raise e

    def extend_expired_positions(self):
        requires_seat = Exists(
            SeatCategoryMapping.objects.filter(
                Q(product=OuterRef('product'))
                & (Q(subevent=OuterRef('subevent')) if self.event.has_subevents else Q(subevent__isnull=True))
            )
        )
        if not self.event.settings.seating_choice:
            requires_seat = Value(0, output_field=IntegerField())
        expired = (
            self.positions.filter(expires__lte=self.now_dt)
            .select_related('product', 'variation', 'voucher', 'addon_to', 'addon_to__product')
            .annotate(requires_seat=requires_seat)
            .prefetch_related('product__quotas', 'variation__quotas', 'addons')
            .order_by('-is_bundled')
        )
        err = None
        changed_prices = {}
        for cp in expired:
            removed_positions = {op.position.pk for op in self._operations if isinstance(op, self.RemoveOperation)}
            if cp.pk in removed_positions or (cp.addon_to_id and cp.addon_to_id in removed_positions):
                continue

            cp.product.requires_seat = self.event.settings.seating_choice and cp.requires_seat

            if cp.is_bundled:
                bundle = cp.addon_to.product.bundles.filter(
                    bundled_product=cp.product, bundled_variation=cp.variation
                ).first()
                if bundle:
                    price = bundle.designated_price or 0
                else:
                    price = cp.price

                changed_prices[cp.pk] = price

                if not cp.includes_tax:
                    price = self._get_price(
                        cp.product,
                        cp.variation,
                        cp.voucher,
                        price,
                        cp.subevent,
                        force_custom_price=True,
                        cp_is_net=False,
                    )
                    price = TaxedPrice(net=price.net, gross=price.net, rate=0, tax=0, name='')
                else:
                    price = self._get_price(
                        cp.product,
                        cp.variation,
                        cp.voucher,
                        price,
                        cp.subevent,
                        force_custom_price=True,
                    )
                pbv = TAXED_ZERO
            else:
                bundled_sum = Decimal('0.00')
                if not cp.addon_to_id:
                    for bundledp in cp.addons.all():
                        if bundledp.is_bundled:
                            bundledprice = changed_prices.get(bundledp.pk, bundledp.price)
                            bundled_sum += bundledprice

                if not cp.includes_tax:
                    price = self._get_price(
                        cp.product,
                        cp.variation,
                        cp.voucher,
                        cp.price,
                        cp.subevent,
                        cp_is_net=True,
                        bundled_sum=bundled_sum,
                    )
                    price = TaxedPrice(net=price.net, gross=price.net, rate=0, tax=0, name='')
                    pbv = self._get_price(
                        cp.product,
                        cp.variation,
                        None,
                        cp.price,
                        cp.subevent,
                        cp_is_net=True,
                        bundled_sum=bundled_sum,
                    )
                    pbv = TaxedPrice(net=pbv.net, gross=pbv.net, rate=0, tax=0, name='')
                else:
                    price = self._get_price(
                        cp.product,
                        cp.variation,
                        cp.voucher,
                        cp.price,
                        cp.subevent,
                        bundled_sum=bundled_sum,
                    )
                    pbv = self._get_price(
                        cp.product,
                        cp.variation,
                        None,
                        cp.price,
                        cp.subevent,
                        bundled_sum=bundled_sum,
                    )

            quotas = list(cp.quotas)
            if not quotas:
                self._operations.append(self.RemoveOperation(position=cp))
                err = error_messages['unavailable']
                continue

            if not cp.voucher or (not cp.voucher.allow_ignore_quota and not cp.voucher.block_quota):
                for quota in quotas:
                    self._quota_diff[quota] += 1
            else:
                quotas = []

            op = self.ExtendOperation(
                position=cp,
                product=cp.product,
                variation=cp.variation,
                voucher=cp.voucher,
                count=1,
                price=price,
                quotas=quotas,
                subevent=cp.subevent,
                seat=cp.seat,
                price_before_voucher=pbv,
            )
            self._check_product_constraints(op)

            if cp.voucher:
                self._voucher_use_diff[cp.voucher] += 1

            self._operations.append(op)
        return err

    def apply_voucher(self, voucher_code: str):
        if self._operations:
            raise CartError('Applying a voucher to the whole cart should not be combined with other operations.')
        try:
            voucher = self.event.vouchers.get(code__iexact=voucher_code.strip())
        except Voucher.DoesNotExist:
            raise CartError(error_messages['voucher_invalid'])
        voucher_use_diff = Counter()
        ops = []

        if not voucher.is_active():
            raise CartError(error_messages['voucher_expired'])

        for p in self.positions:
            if p.voucher_id:
                continue

            if not voucher.applies_to(p.product, p.variation):
                continue

            if voucher.seat and voucher.seat != p.seat:
                continue

            if voucher.subevent_id and voucher.subevent_id != p.subevent_id:
                continue

            if p.is_bundled:
                continue

            bundled_sum = Decimal('0.00')
            if not p.addon_to_id:
                for bundledp in p.addons.all():
                    if bundledp.is_bundled:
                        bundledprice = bundledp.price
                        bundled_sum += bundledprice

            price = self._get_price(p.product, p.variation, voucher, None, p.subevent, bundled_sum=bundled_sum)
            """
            if price.gross > p.price:
                continue
            """

            voucher_use_diff[voucher] += 1
            ops.append((p.price - price.gross, self.VoucherOperation(p, voucher, price)))

        # If there are not enough voucher usages left for the full cart, let's apply them in the order that benefits
        # the user the most.
        ops.sort(key=lambda k: k[0], reverse=True)
        self._operations += [k[1] for k in ops]
        if not voucher_use_diff:
            raise CartError(error_messages['voucher_no_match'])
        self._voucher_use_diff += voucher_use_diff

    def add_new_products(self, products: List[dict]):
        # Fetch products from the database
        self._update_products_cache([i['product'] for i in products], [i['variation'] for i in products])
        self._update_subevents_cache([i['subevent'] for i in products if i.get('subevent')])
        quota_diff = Counter()
        voucher_use_diff = Counter()
        operations = []

        for i in products:
            if self.event.has_subevents:
                if not i.get('subevent') or int(i.get('subevent')) not in self._subevents_cache:
                    raise CartError(error_messages['subevent_required'])
                subevent = self._subevents_cache[int(i.get('subevent'))]
            else:
                subevent = None

            # When a seat is given, we ignore the product that was given, since we can infer it from the
            # seat. The variation is still relevant, though!
            seat = None
            if i.get('seat'):
                try:
                    seat = (subevent or self.event).seats.get(seat_guid=i.get('seat'))
                except Seat.DoesNotExist:
                    raise CartError(error_messages['seat_invalid'])
                except Seat.MultipleObjectsReturned:
                    raise CartError(error_messages['seat_invalid'])
                i['product'] = seat.product_id
                if i['product'] not in self._products_cache:
                    self._update_products_cache([i['product']], [i['variation']])

            # Check whether the specified products are part of what we just fetched from the database
            # If they are not, the user supplied product IDs which either do not exist or belong to
            # a different event
            if i['product'] not in self._products_cache or (
                i['variation'] and i['variation'] not in self._variations_cache
            ):
                raise CartError(error_messages['not_for_sale'])

            product = self._products_cache[i['product']]
            variation = self._variations_cache[i['variation']] if i['variation'] is not None else None
            voucher = None

            if i.get('voucher'):
                try:
                    voucher = self.event.vouchers.get(code__iexact=i.get('voucher').strip())
                except Voucher.DoesNotExist:
                    raise CartError(error_messages['voucher_invalid'])
                else:
                    voucher_use_diff[voucher] += i['count']

            # Fetch all quotas. If there are no quotas, this product is not allowed to be sold.
            quotas = list(
                product.quotas.filter(subevent=subevent)
                if variation is None
                else variation.quotas.filter(subevent=subevent)
            )
            if not quotas:
                raise CartError(error_messages['unavailable'])
            if not voucher or (not voucher.allow_ignore_quota and not voucher.block_quota):
                for quota in quotas:
                    quota_diff[quota] += i['count']
            else:
                quotas = []

            # Fetch bundled products
            bundled = []
            bundled_sum = Decimal('0.00')
            db_bundles = list(product.bundles.all())
            self._update_products_cache(
                [b.bundled_product_id for b in db_bundles],
                [b.bundled_variation_id for b in db_bundles],
            )
            for bundle in db_bundles:
                if bundle.bundled_product_id not in self._products_cache or (
                    bundle.bundled_variation_id and bundle.bundled_variation_id not in self._variations_cache
                ):
                    raise CartError(error_messages['not_for_sale'])
                bproduct = self._products_cache[bundle.bundled_product_id]
                bvar = self._variations_cache[bundle.bundled_variation_id] if bundle.bundled_variation_id else None
                bundle_quotas = list(
                    bproduct.quotas.filter(subevent=subevent) if bvar is None else bvar.quotas.filter(subevent=subevent)
                )
                if not bundle_quotas:
                    raise CartError(error_messages['unavailable'])
                if not voucher or not voucher.allow_ignore_quota:
                    for quota in bundle_quotas:
                        quota_diff[quota] += bundle.count * i['count']
                else:
                    bundle_quotas = []

                if bundle.designated_price:
                    bprice = self._get_price(
                        bproduct,
                        bvar,
                        None,
                        bundle.designated_price,
                        subevent,
                        force_custom_price=True,
                        cp_is_net=False,
                    )
                else:
                    bprice = TAXED_ZERO
                bundled_sum += bundle.designated_price * bundle.count

                bop = self.AddOperation(
                    count=bundle.count,
                    product=bproduct,
                    variation=bvar,
                    price=bprice,
                    voucher=None,
                    quotas=bundle_quotas,
                    addon_to='FAKE',
                    subevent=subevent,
                    includes_tax=bool(bprice.rate),
                    bundled=[],
                    seat=None,
                    price_before_voucher=bprice,
                )
                self._check_product_constraints(bop, operations)
                bundled.append(bop)

            price = self._get_price(
                product,
                variation,
                voucher,
                i.get('price'),
                subevent,
                bundled_sum=bundled_sum,
            )
            pbv = self._get_price(product, variation, None, i.get('price'), subevent, bundled_sum=bundled_sum)

            op = self.AddOperation(
                count=i['count'],
                product=product,
                variation=variation,
                price=price,
                voucher=voucher,
                quotas=quotas,
                addon_to=False,
                subevent=subevent,
                includes_tax=bool(price.rate),
                bundled=bundled,
                seat=seat,
                price_before_voucher=pbv,
            )
            self._check_product_constraints(op, operations)
            operations.append(op)

        self._quota_diff.update(quota_diff)
        self._voucher_use_diff += voucher_use_diff
        self._operations += operations

    def remove_product(self, pos_id: int):
        # TODO: We could calculate quotadiffs and voucherdiffs here, which would lead to more
        # flexible usages (e.g. a RemoveOperation and an AddOperation in the same transaction
        # could cancel each other out quota-wise). However, we are not taking this performance
        # penalty for now as there is currently no outside interface that would allow building
        # such a transaction.
        try:
            cp = self.positions.get(pk=pos_id)
        except CartPosition.DoesNotExist:
            raise CartError(error_messages['unknown_position'])
        self._operations.append(self.RemoveOperation(position=cp))

    def clear(self):
        # TODO: We could calculate quotadiffs and voucherdiffs here, which would lead to more
        # flexible usages (e.g. a RemoveOperation and an AddOperation in the same transaction
        # could cancel each other out quota-wise). However, we are not taking this performance
        # penalty for now as there is currently no outside interface that would allow building
        # such a transaction.
        for cp in self.positions.filter(addon_to__isnull=True):
            self._operations.append(self.RemoveOperation(position=cp))

    def set_addons(self, addons):
        self._update_products_cache(
            [a['product'] for a in addons],
            [a['variation'] for a in addons],
        )

        # Prepare various containers to hold data later
        current_addons = defaultdict(lambda: defaultdict(list))  # CartPos -> currently attached add-ons
        input_addons = defaultdict(Counter)  # CartPos -> final desired set of add-ons
        selected_addons = defaultdict(Counter)  # CartPos, ProductAddOn -> final desired set of add-ons
        cpcache = {}  # CartPos.pk -> CartPos
        quota_diff = Counter()  # Quota -> Number of usages
        operations = []
        available_categories = defaultdict(set)  # CartPos -> Category IDs to choose from
        price_included = defaultdict(dict)  # CartPos -> CategoryID -> bool(price is included)
        toplevel_cp = (
            self.positions.filter(addon_to__isnull=True)
            .prefetch_related('addons', 'product__addons', 'product__addons__addon_category')
            .select_related('product', 'variation')
        )

        # Prefill some of the cache containers
        for cp in toplevel_cp:
            available_categories[cp.pk] = {iao.addon_category_id for iao in cp.product.addons.all()}
            price_included[cp.pk] = {iao.addon_category_id: iao.price_included for iao in cp.product.addons.all()}
            cpcache[cp.pk] = cp
            for a in cp.addons.all():
                if not a.is_bundled:
                    current_addons[cp][a.product_id, a.variation_id].append(a)

        # Create operations, perform various checks
        for a in addons:
            # Check whether the specified products are part of what we just fetched from the database
            # If they are not, the user supplied product IDs which either do not exist or belong to
            # a different event
            if a['product'] not in self._products_cache or (
                a['variation'] and a['variation'] not in self._variations_cache
            ):
                raise CartError(error_messages['not_for_sale'])

            # Only attach addons to things that are actually in this user's cart
            if a['addon_to'] not in cpcache:
                raise CartError(error_messages['addon_invalid_base'])

            cp = cpcache[a['addon_to']]
            product = self._products_cache[a['product']]
            variation = self._variations_cache[a['variation']] if a['variation'] is not None else None

            if product.category_id not in available_categories[cp.pk]:
                raise CartError(error_messages['addon_invalid_base'])

            # Fetch all quotas. If there are no quotas, this product is not allowed to be sold.
            quotas = list(
                product.quotas.filter(subevent=cp.subevent)
                if variation is None
                else variation.quotas.filter(subevent=cp.subevent)
            )
            if not quotas:
                raise CartError(error_messages['unavailable'])

            if (a['product'], a['variation']) in input_addons[cp.id]:
                raise CartError(error_messages['addon_duplicate_product'])

            input_addons[cp.id][a['product'], a['variation']] = a.get('count', 1)
            selected_addons[cp.id, product.category_id][a['product'], a['variation']] = a.get('count', 1)

            if price_included[cp.pk].get(product.category_id):
                price = TAXED_ZERO
            else:
                price = self._get_price(product, variation, None, a.get('price'), cp.subevent)

            # Fix positions with wrong price (TODO: happens out-of-cartmanager-transaction and therefore a little hacky)
            for ca in current_addons[cp][a['product'], a['variation']]:
                if ca.price != price.gross:
                    ca.price = price.gross
                    ca.save(update_fields=['price'])

            if a.get('count', 1) > len(current_addons[cp][a['product'], a['variation']]):
                # This add-on is new, add it to the cart
                for quota in quotas:
                    quota_diff[quota] += a.get('count', 1) - len(current_addons[cp][a['product'], a['variation']])

                op = self.AddOperation(
                    count=a.get('count', 1) - len(current_addons[cp][a['product'], a['variation']]),
                    product=product,
                    variation=variation,
                    price=price,
                    voucher=None,
                    quotas=quotas,
                    addon_to=cp,
                    subevent=cp.subevent,
                    includes_tax=bool(price.rate),
                    bundled=[],
                    seat=None,
                    price_before_voucher=None,
                )
                self._check_product_constraints(op, operations)
                operations.append(op)

        # Check constraints on the add-on combinations
        for cp in toplevel_cp:
            product = cp.product
            for iao in product.addons.all():
                selected = selected_addons[cp.id, iao.addon_category_id]
                n_per_i = Counter()
                for (i, v), c in selected.products():
                    n_per_i[i] += c
                if sum(selected.values()) > iao.max_count:
                    # TODO: Proper i18n
                    # TODO: Proper pluralization
                    raise CartError(
                        error_messages['addon_max_count'],
                        {
                            'base': str(product.name),
                            'max': iao.max_count,
                            'cat': str(iao.addon_category.name),
                        },
                    )
                elif sum(selected.values()) < iao.min_count:
                    # TODO: Proper i18n
                    # TODO: Proper pluralization
                    raise CartError(
                        error_messages['addon_min_count'],
                        {
                            'base': str(product.name),
                            'min': iao.min_count,
                            'cat': str(iao.addon_category.name),
                        },
                    )
                elif any(v > 1 for v in n_per_i.values()) and not iao.multi_allowed:
                    raise CartError(
                        error_messages['addon_no_multi'],
                        {
                            'base': str(product.name),
                            'cat': str(iao.addon_category.name),
                        },
                    )
                validate_cart_addons.send(
                    sender=self.event,
                    addons={
                        (
                            self._products_cache[s[0]],
                            self._variations_cache[s[1]] if s[1] else None,
                        ): c
                        for s, c in selected.items()
                        if c > 0
                    },
                    base_position=cp,
                    iao=iao,
                )

        # Detect removed add-ons and create RemoveOperations
        for cp, al in list(current_addons.items()):
            for k, v in al.items():
                input_num = input_addons[cp.id].get(k, 0)
                current_num = len(current_addons[cp].get(k, []))
                if input_num < current_num:
                    for a in current_addons[cp][k][: current_num - input_num]:
                        if a.expires > self.now_dt:
                            quotas = list(a.quotas)

                            for quota in quotas:
                                quota_diff[quota] -= 1

                        op = self.RemoveOperation(position=a)
                        operations.append(op)

        self._quota_diff.update(quota_diff)
        self._operations += operations

    def _get_quota_availability(self):
        quotas_ok = defaultdict(int)
        qa = QuotaAvailability()
        qa.queue(*[k for k, v in self._quota_diff.items() if v > 0])
        qa.compute(now_dt=self.now_dt)
        for quota, count in self._quota_diff.items():
            if count <= 0:
                quotas_ok[quota] = 0
                break
            avail = qa.results[quota]
            if avail[1] is not None and avail[1] < count:
                quotas_ok[quota] = min(count, avail[1])
            else:
                quotas_ok[quota] = count
        return quotas_ok

    def _get_voucher_availability(self):
        vouchers_ok = {}
        self._voucher_depend_on_cart = set()
        for voucher, count in self._voucher_use_diff.items():
            voucher.refresh_from_db()

            if voucher.valid_until is not None and voucher.valid_until < self.now_dt:
                raise CartError(error_messages['voucher_expired'])

            redeemed_in_carts = CartPosition.objects.filter(
                Q(voucher=voucher) & Q(event=self.event) & Q(expires__gte=self.now_dt)
            ).exclude(pk__in=[op.position.id for op in self._operations if isinstance(op, self.ExtendOperation)])
            cart_count = redeemed_in_carts.count()
            v_avail = voucher.max_usages - voucher.redeemed - cart_count
            if cart_count > 0:
                self._voucher_depend_on_cart.add(voucher)
            vouchers_ok[voucher] = v_avail

        return vouchers_ok

    def _check_min_max_per_product(self):
        products = Counter()
        for p in self.positions:
            products[p.product] += 1
        for op in self._operations:
            if isinstance(op, self.AddOperation):
                products[op.product] += op.count
            elif isinstance(op, self.RemoveOperation):
                products[op.position.product] -= 1

        err = None
        for product, count in products.items():
            if count == 0:
                continue

            if product.max_per_order and count > product.max_per_order:
                raise CartError(
                    _(error_messages['max_products_per_product'])
                    % {'max': product.max_per_order, 'product': product.name}
                )

            if product.min_per_order and count < product.min_per_order:
                self._operations = [
                    o for o in self._operations if not (isinstance(o, self.AddOperation) and o.product.pk == product.pk)
                ]
                removals = [o.position.pk for o in self._operations if isinstance(o, self.RemoveOperation)]
                for p in self.positions:
                    if p.product_id == product.pk and p.pk not in removals:
                        self._operations.append(self.RemoveOperation(position=p))
                        err = _(error_messages['min_products_per_product_removed']) % {
                            'min': product.min_per_order,
                            'product': product.name,
                        }
                if not err:
                    raise CartError(
                        _(error_messages['min_products_per_product'])
                        % {'min': product.min_per_order, 'product': product.name}
                    )
        return err

    def _check_one_ticket_per_user(self):
        """
        Enforce per-product "one ticket per user" restriction:
        - If a product has the meta flag enabled, the user cannot have more than one
          of that product in their cart, and if an email is present, also cannot have
          an existing paid/pending order for that product.
        - Adjusts quantities to 1 instead of blocking the operation.
        """
        # Build per-product counts from current cart positions
        per_product_counts = Counter(p.product_id for p in self.positions)

        # Apply pending operations to get the final intended counts
        for op in self._operations:
            if isinstance(op, self.AddOperation):
                per_product_counts[op.product.id] += op.count
            elif isinstance(op, self.RemoveOperation):
                if op.position:
                    per_product_counts[op.position.product_id] -= 1

        # For all affected products, check meta flag and enforce max 1
        affected_product_ids = set(per_product_counts.keys())
        if not affected_product_ids:
            return None

        # Find which of the affected products have the flag set via meta
        flagged_product_ids = set(
            ProductMetaValue.objects.filter(
                product_id__in=affected_product_ids,
                property__name='limit_one_per_user',
            ).values_list('product_id', flat=True)
        )

        # Adjust quantities for flagged products that exceed 1
        # Only products with the 'limit_one_per_user' meta property are affected
        quantity_adjusted = False
        for i, op in enumerate(self._operations):
            if isinstance(op, self.AddOperation) and op.product.id in flagged_product_ids:
                # This product has the limit_one_per_user flag, check if total would exceed 1
                final_count = per_product_counts.get(op.product.id, 0)
                if final_count > 1:
                    # Calculate how many are currently in cart (before this operation)
                    current_count = final_count - op.count
                    # Calculate maximum additional items that can be added (to reach total of 1)
                    max_additional = max(0, 1 - current_count)
                    if op.count > max_additional:
                        # Replace the operation with adjusted count
                        self._operations[i] = op._replace(count=max_additional)
                        quantity_adjusted = True

        # If we have an email, also check existing orders for flagged products
        email = None
        if hasattr(self, 'invoice_address') and self.invoice_address and self.invoice_address.email:
            email = self.invoice_address.email

        if email and flagged_product_ids:
            exists = OrderPosition.objects.filter(
                order__event=self.event,
                order__email=email,
                order__status__in=[Order.STATUS_PENDING, Order.STATUS_PAID],
                product_id__in=flagged_product_ids,
            ).exists()
            if exists:
                return error_messages['one_ticket_per_user']

        # Return warning message if quantity was adjusted
        if quantity_adjusted:
            return error_messages['one_ticket_per_user_cart']

        return None

    def _perform_operations(self):
        vouchers_ok = self._get_voucher_availability()
        quotas_ok = self._get_quota_availability()
        err = None
        warning = None
        new_cart_positions = []

        err = err or self._check_min_max_per_product()
        warning = self._check_one_ticket_per_user()
        # Only treat as error if it's not a quantity adjustment warning
        if warning and warning != error_messages['one_ticket_per_user_cart']:
            err = err or warning
            warning = None

        self._operations.sort(key=lambda a: self.order[type(a)])
        seats_seen = set()

        for iop, op in enumerate(self._operations):
            if isinstance(op, self.RemoveOperation):
                if op.position.expires > self.now_dt:
                    for q in op.position.quotas:
                        quotas_ok[q] += 1
                op.position.addons.all().delete()
                op.position.delete()

            elif isinstance(op, (self.AddOperation, self.ExtendOperation)):
                # Create a CartPosition for as much products as we can
                requested_count = quota_available_count = voucher_available_count = op.count

                if op.seat:
                    if op.seat in seats_seen:
                        err = err or error_messages['seat_multiple']
                    seats_seen.add(op.seat)

                if op.quotas:
                    quota_available_count = min(requested_count, min(quotas_ok[q] for q in op.quotas))

                if op.voucher:
                    voucher_available_count = min(voucher_available_count, vouchers_ok[op.voucher])

                if quota_available_count < 1:
                    err = err or error_messages['unavailable']
                elif quota_available_count < requested_count:
                    err = err or error_messages['in_part']

                if voucher_available_count < 1:
                    if op.voucher in self._voucher_depend_on_cart:
                        err = err or error_messages['voucher_redeemed_cart'] % self.event.settings.reservation_time
                    else:
                        err = err or error_messages['voucher_redeemed']
                elif voucher_available_count < requested_count:
                    err = err or error_messages['voucher_redeemed_partial'] % voucher_available_count

                available_count = min(quota_available_count, voucher_available_count)

                if isinstance(op, self.AddOperation):
                    for b in op.bundled:
                        b_quotas = list(b.quotas)
                        if not b_quotas:
                            if not op.voucher or not op.voucher.allow_ignore_quota:
                                err = err or error_messages['unavailable']
                                available_count = 0
                            continue
                        b_quota_available_count = min(
                            available_count * b.count,
                            min(quotas_ok[q] for q in b_quotas),
                        )
                        if b_quota_available_count < b.count:
                            err = err or error_messages['unavailable']
                            available_count = 0
                        elif b_quota_available_count < available_count * b.count:
                            err = err or error_messages['in_part']
                            available_count = b_quota_available_count // b.count
                        for q in b_quotas:
                            quotas_ok[q] -= available_count * b.count
                            # TODO: is this correct?

                for q in op.quotas:
                    quotas_ok[q] -= available_count
                if op.voucher:
                    vouchers_ok[op.voucher] -= available_count

                if any(qa < 0 for qa in quotas_ok.values()):
                    # Safeguard, shouldn't happen
                    err = err or error_messages['unavailable']
                    available_count = 0

                if isinstance(op, self.AddOperation):
                    if op.seat and not op.seat.is_available(
                        ignore_voucher_id=op.voucher.id if op.voucher else None,
                        sales_channel=self._sales_channel,
                        distance_ignore_cart_id=self.cart_id,
                    ):
                        available_count = 0
                        err = err or error_messages['seat_unavailable']

                    for k in range(available_count):
                        cp = CartPosition(
                            event=self.event,
                            product=op.product,
                            variation=op.variation,
                            price=op.price.gross,
                            expires=self._expiry,
                            cart_id=self.cart_id,
                            voucher=op.voucher,
                            addon_to=op.addon_to if op.addon_to else None,
                            subevent=op.subevent,
                            includes_tax=op.includes_tax,
                            seat=op.seat,
                            override_tax_rate=op.price.rate,
                            price_before_voucher=op.price_before_voucher.gross
                            if op.price_before_voucher is not None
                            else None,
                        )
                        if self.event.settings.attendee_names_asked:
                            scheme = PERSON_NAME_SCHEMES.get(self.event.settings.name_scheme)
                            if 'attendee-name' in self._widget_data:
                                cp.attendee_name_parts = {'_legacy': self._widget_data['attendee-name']}
                            if any(
                                'attendee-name-{}'.format(k.replace('_', '-')) in self._widget_data
                                for k, l, w in scheme['fields']
                            ):
                                cp.attendee_name_parts = {
                                    k: self._widget_data.get(
                                        'attendee-name-{}'.format(k.replace('_', '-')),
                                        '',
                                    )
                                    for k, l, w in scheme['fields']
                                }
                        if self.event.settings.attendee_emails_asked and 'email' in self._widget_data:
                            cp.attendee_email = self._widget_data.get('email')

                        cp._answers = {}
                        for k, v in self._widget_data.items():
                            if not k.startswith('question-'):
                                continue
                            q = cp.product.questions.filter(ask_during_checkin=False, identifier__iexact=k[9:]).first()
                            if q:
                                try:
                                    cp._answers[q] = q.clean_answer(v)
                                except ValidationError:
                                    pass

                        if op.bundled:
                            cp.save()  # Needs to be in the database already so we have a PK that we can reference
                            for b in op.bundled:
                                for j in range(b.count):
                                    new_cart_positions.append(
                                        CartPosition(
                                            event=self.event,
                                            product=b.product,
                                            variation=b.variation,
                                            price=b.price.gross,
                                            expires=self._expiry,
                                            cart_id=self.cart_id,
                                            voucher=None,
                                            addon_to=cp,
                                            override_tax_rate=b.price.rate,
                                            subevent=b.subevent,
                                            includes_tax=b.includes_tax,
                                            is_bundled=True,
                                        )
                                    )

                        new_cart_positions.append(cp)
                elif isinstance(op, self.ExtendOperation):
                    if op.seat and not op.seat.is_available(
                        ignore_cart=op.position,
                        sales_channel=self._sales_channel,
                        ignore_voucher_id=op.position.voucher_id,
                    ):
                        err = err or error_messages['seat_unavailable']
                        op.position.addons.all().delete()
                        op.position.delete()
                    elif available_count == 1:
                        op.position.expires = self._expiry
                        op.position.price = op.price.gross
                        if op.price_before_voucher is not None:
                            op.position.price_before_voucher = op.price_before_voucher.gross
                        try:
                            op.position.save(force_update=True)
                        except DatabaseError:
                            # Best effort... The position might have been deleted in the meantime!
                            pass
                    elif available_count == 0:
                        op.position.addons.all().delete()
                        op.position.delete()
                    else:
                        raise AssertionError('ExtendOperation cannot affect more than one product')
            elif isinstance(op, self.VoucherOperation):
                if vouchers_ok[op.voucher] < 1:
                    if iop == 0:
                        raise CartError(error_messages['voucher_redeemed'])
                    else:
                        # We fail silently if we could only apply the voucher to part of the cart, since that might
                        # be expected
                        continue

                op.position.price_before_voucher = op.position.price
                op.position.price = op.price.gross
                op.position.voucher = op.voucher
                op.position.save()
                vouchers_ok[op.voucher] -= 1

        for p in new_cart_positions:
            if getattr(p, '_answers', None):
                if not p.pk:  # We stored some to the database already before
                    p.save()
                _save_answers(p, {}, p._answers)
        CartPosition.objects.bulk_create(
            [p for p in new_cart_positions if not getattr(p, '_answers', None) and not p.pk]
        )
        return err, warning

    def _require_locking(self):
        if self._voucher_use_diff:
            # If any vouchers are used, we lock to make sure we don't redeem them to often
            return True

        if self._quota_diff and any(q.size is not None for q in self._quota_diff):
            # If any quotas are affected that are not unlimited, we lock
            return True

        if any(getattr(o, 'seat', False) for o in self._operations):
            return True

        return False

    def commit(self):
        self._check_presale_dates()
        self._check_max_cart_size()
        self._calculate_expiry()

        err = self._delete_out_of_timeframe()
        err = self.extend_expired_positions() or err

        lockfn = NoLockManager
        if self._require_locking():
            lockfn = self.event.lock

        with lockfn() as now_dt:
            with transaction.atomic():
                self.now_dt = now_dt
                self._extend_expiry_of_valid_existing_positions()
                err, warning = self._perform_operations()
                err = err or err
            if err:
                raise CartError(err)
            # Store warning for later retrieval if needed
            if warning:
                self._last_warning = warning


def update_tax_rates(event: Event, cart_id: str, invoice_address: InvoiceAddress):
    positions = CartPosition.objects.filter(cart_id=cart_id, event=event).select_related('product', 'product__tax_rule')
    totaldiff = Decimal('0.00')
    for pos in positions:
        if not pos.product.tax_rule:
            continue
        rate = pos.product.tax_rule.tax_rate_for(invoice_address)

        if pos.tax_rate != rate:
            current_net = pos.price - pos.tax_value
            new_gross = pos.product.tax(current_net, base_price_is='net', invoice_address=invoice_address).gross
            totaldiff += new_gross - pos.price
            pos.price = new_gross
            pos.includes_tax = rate != Decimal('0.00')
            pos.override_tax_rate = rate
            pos.save(update_fields=['price', 'includes_tax', 'override_tax_rate'])

    return totaldiff


def get_fees(event, request, total, invoice_address, provider, positions):
    from eventyay.presale.views.cart import cart_session

    fees = []
    for recv, resp in fee_calculation_for_cart.send(
        sender=event,
        request=request,
        invoice_address=invoice_address,
        total=total,
        positions=positions,
    ):
        if resp:
            fees += resp

    total = total + sum(f.value for f in fees)

    cs = cart_session(request)
    if cs.get('gift_cards'):
        gcs = cs['gift_cards']
        gc_qs = event.organizer.accepted_gift_cards.filter(pk__in=cs.get('gift_cards'), currency=event.currency)
        for gc in gc_qs:
            if gc.testmode != event.testmode:
                gcs.remove(gc.pk)
                continue
            fval = Decimal(gc.value)  # TODO: don't require an extra query
            fval = min(fval, total)
            if fval > 0:
                total -= fval
                fees.append(
                    OrderFee(
                        fee_type=OrderFee.FEE_TYPE_GIFTCARD,
                        internal_type='giftcard',
                        description=gc.secret,
                        value=-1 * fval,
                        tax_rate=Decimal('0.00'),
                        tax_value=Decimal('0.00'),
                        tax_rule=TaxRule.zero(),
                    )
                )
        cs['gift_cards'] = gcs

    if provider and total != 0:
        provider = event.get_payment_providers().get(provider)
        if provider:
            payment_fee = provider.calculate_fee(total)

            if payment_fee:
                payment_fee_tax_rule = event.settings.tax_rate_default or TaxRule.zero()
                payment_fee_tax = payment_fee_tax_rule.tax(
                    payment_fee, base_price_is='gross', invoice_address=invoice_address
                )
                fees.append(
                    OrderFee(
                        fee_type=OrderFee.FEE_TYPE_PAYMENT,
                        value=payment_fee,
                        tax_rate=payment_fee_tax.rate,
                        tax_value=payment_fee_tax.tax,
                        tax_rule=payment_fee_tax_rule,
                    )
                )

    return fees


@app.task(
    base=ProfiledEventTask,
    bind=True,
    max_retries=5,
    default_retry_delay=1,
    throws=(CartError,),
)
def add_products_to_cart(
    self,
    event: int,
    products: List[dict],
    cart_id: str = None,
    locale='en',
    invoice_address: int = None,
    widget_data=None,
    sales_channel='web',
) -> dict:
    """
    Adds a list of products to a user's cart.
    :param event: The event ID in question
    :param products: A list of dicts with the keys product, variation, count, custom_price, voucher, seat ID
    :param cart_id: Session ID of a guest
    :raises CartError: On any error that occurred
    :returns: Dict with success status and optional warning message
    """
    with language(locale):
        ia = False
        if invoice_address:
            try:
                with scopes_disabled():
                    ia = InvoiceAddress.objects.get(pk=invoice_address)
            except InvoiceAddress.DoesNotExist:
                pass

        try:
            try:
                cm = CartManager(
                    event=event,
                    cart_id=cart_id,
                    invoice_address=ia,
                    widget_data=widget_data,
                    sales_channel=sales_channel,
                )
                cm.add_new_products(products)
                cm.commit()
                
                # Check if there was a warning about quantity adjustment
                warning = cm.get_last_warning()
                if warning:
                    return {'success': True, 'warning': str(warning)}
                else:
                    return {'success': True}
                    
            except LockTimeoutException:
                self.retry()
        except (MaxRetriesExceededError, LockTimeoutException):
            raise CartError(error_messages['busy'])


@app.task(
    base=ProfiledEventTask,
    bind=True,
    max_retries=5,
    default_retry_delay=1,
    throws=(CartError,),
)
def apply_voucher(
    self,
    event: Event,
    voucher: str,
    cart_id: str = None,
    locale='en',
    sales_channel='web',
) -> None:
    """
    Removes a list of products from a user's cart.
    :param event: The event ID in question
    :param voucher: A voucher code
    :param session: Session ID of a guest
    """
    with language(locale):
        try:
            try:
                cm = CartManager(event=event, cart_id=cart_id, sales_channel=sales_channel)
                cm.apply_voucher(voucher)
                cm.commit()
            except LockTimeoutException:
                self.retry()
        except (MaxRetriesExceededError, LockTimeoutException):
            raise CartError(error_messages['busy'])


@app.task(
    base=ProfiledEventTask,
    bind=True,
    max_retries=5,
    default_retry_delay=1,
    throws=(CartError,),
)
def remove_cart_position(
    self,
    event: Event,
    position: int,
    cart_id: str = None,
    locale='en',
    sales_channel='web',
) -> None:
    """
    Removes a list of products from a user's cart.
    :param event: The event ID in question
    :param position: A cart position ID
    :param session: Session ID of a guest
    """
    with language(locale):
        try:
            try:
                cm = CartManager(event=event, cart_id=cart_id, sales_channel=sales_channel)
                cm.remove_product(position)
                cm.commit()
            except LockTimeoutException:
                self.retry()
        except (MaxRetriesExceededError, LockTimeoutException):
            raise CartError(error_messages['busy'])


@app.task(
    base=ProfiledEventTask,
    bind=True,
    max_retries=5,
    default_retry_delay=1,
    throws=(CartError,),
)
def clear_cart(self, event: Event, cart_id: str = None, locale='en', sales_channel='web') -> None:
    """
    Removes a list of products from a user's cart.
    :param event: The event ID in question
    :param session: Session ID of a guest
    """
    with language(locale):
        try:
            try:
                cm = CartManager(event=event, cart_id=cart_id, sales_channel=sales_channel)
                cm.clear()
                cm.commit()
            except LockTimeoutException:
                self.retry()
        except (MaxRetriesExceededError, LockTimeoutException):
            raise CartError(error_messages['busy'])


@app.task(
    base=ProfiledEventTask,
    bind=True,
    max_retries=5,
    default_retry_delay=1,
    throws=(CartError,),
)
def set_cart_addons(
    self,
    event: Event,
    addons: List[dict],
    cart_id: str = None,
    locale='en',
    invoice_address: int = None,
    sales_channel='web',
) -> None:
    """
    Removes a list of products from a user's cart.
    :param event: The event ID in question
    :param addons: A list of dicts with the keys addon_to, product, variation
    :param session: Session ID of a guest
    """
    with language(locale):
        ia = False
        if invoice_address:
            try:
                with scopes_disabled():
                    ia = InvoiceAddress.objects.get(pk=invoice_address)
            except InvoiceAddress.DoesNotExist:
                pass
        try:
            try:
                cm = CartManager(
                    event=event,
                    cart_id=cart_id,
                    invoice_address=ia,
                    sales_channel=sales_channel,
                )
                cm.set_addons(addons)
                cm.commit()
            except LockTimeoutException:
                self.retry()
        except (MaxRetriesExceededError, LockTimeoutException):
            raise CartError(error_messages['busy'])


@receiver(checkout_confirm_messages, dispatch_uid='cart_confirm_messages')
def confirm_messages(sender, *args, **kwargs):
    if not sender.settings.confirm_texts:
        return {}
    confirm_texts = sender.settings.get('confirm_texts', as_type=LazyI18nStringList)
    return {'confirm_text_%i' % index: rich_text(str(text)) for index, text in enumerate(confirm_texts)}
