from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Tuple

from django.db.models import (
    Case,
    Count,
    DateTimeField,
    F,
    Max,
    OuterRef,
    Subquery,
    Sum,
    Value,
    When,
)
from django.utils.timezone import make_aware
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, Product, ProductCategory, Order, OrderPosition
from eventyay.base.models.event import SubEvent
from eventyay.base.models.orders import OrderFee, OrderPayment
from eventyay.base.signals import order_fee_type_name


class DummyObject:
    def __str__(self):
        return str(self.name)


class Dontsum:
    def __init__(self, value: Any):
        self.value = value

    def __str__(self) -> str:
        return str(self.value)


def tuplesum(tuples: Iterable[Tuple]) -> Tuple:
    """
    Takes a list of tuples of size n. In our case, those are e.g. tuples of size 2 containing
    a number of sales and a sum of their toal amount.

    Returned is again a tuple of size n. The first component of the returned tuple is the
    sum of the first components of all input tuples.

    Sample:

    >>> tuplesum([(1, 2), (3, 4), (5, 6)])
    (9, 12)
    """

    def mysum(it):
        # This method is identical to sum(list), except that it ignores entries of the type
        # Dontsum. We need this because we list the payment method fees seperately but we don't
        # want a order to contribute twice to the total count of orders (once for a product
        # and once for the payment method fee).
        sit = [i for i in it if not isinstance(i, Dontsum)]
        return sum(sit)

    # zip(*list(tuples)) basically transposes our input, e.g. [(1,2), (3,4), (5,6)]
    # becomes [(1, 3, 5), (2, 4, 6)]. We then call map on that, such that mysum((1, 3, 5))
    # and mysum((2, 4, 6)) will be called. The results will then be combined in a tuple again.
    return tuple(map(mysum, zip(*list(tuples))))


def dictsum(*dicts) -> dict:
    """
    Takes multiple dictionaries as arguments and builds a new dict. The input dict is expected
    to be a mapping of keys to tuples. The output dict will contain all keys that are
    present in any of the input dicts and will contain the tuplesum of all values associated
    with this key (see tuplesum function).

    Sample:

    >>> dictsum({'a': (1, 2), 'b': (3, 4)}, {'a': (5, 6), 'c': (7, 8)})
    {'a': (6, 8), 'b': (3, 4), 'c': (7, 8)}
    """
    res = {}
    keys = set()
    for d in dicts:
        keys |= set(d.keys())
    for k in keys:
        res[k] = tuplesum(d[k] for d in dicts if k in d)
    return res


def order_overview(
    event: Event,
    subevent: SubEvent = None,
    date_filter='',
    date_from=None,
    date_until=None,
    fees=False,
    admission_only=False,
) -> Tuple[List[Tuple[ProductCategory, List[Product]]], Dict[str, Tuple[Decimal, Decimal]]]:
    products = (
        event.products.all()
        .select_related(
            'category',  # for re-grouping
        )
        .prefetch_related('variations')
        .order_by('category__position', 'category_id', 'position', 'name')
    )

    qs = OrderPosition.all
    if subevent:
        qs = qs.filter(subevent=subevent)
    if admission_only:
        qs = qs.filter(product__admission=True)
        products = products.filter(admission=True)

    if date_from and isinstance(date_from, date):
        date_from = make_aware(
            datetime.combine(date_from, time(hour=0, minute=0, second=0, microsecond=0)),
            event.timezone,
        )

    if date_until and isinstance(date_until, date):
        date_until = make_aware(
            datetime.combine(
                date_until + timedelta(days=1),
                time(hour=0, minute=0, second=0, microsecond=0),
            ),
            event.timezone,
        )

    if date_filter == 'order_date':
        if date_from:
            qs = qs.filter(order__datetime__gte=date_from)
        if date_until:
            qs = qs.filter(order__datetime__lt=date_until)
    elif date_filter == 'last_payment_date':
        p_date = (
            OrderPayment.objects.filter(
                order=OuterRef('order'),
                state__in=[
                    OrderPayment.PAYMENT_STATE_CONFIRMED,
                    OrderPayment.PAYMENT_STATE_REFUNDED,
                ],
                payment_date__isnull=False,
            )
            .values('order')
            .annotate(m=Max('payment_date'))
            .values('m')
            .order_by()
        )
        qs = qs.annotate(payment_date=Subquery(p_date, output_field=DateTimeField()))
        if date_from:
            qs = qs.filter(payment_date__gte=date_from)
        if date_until:
            qs = qs.filter(payment_date__lt=date_until)

    counters = (
        qs.filter(order__event=event)
        .annotate(
            status=Case(
                When(
                    order__status='n',
                    order__require_approval=True,
                    then=Value('unapproved'),
                ),
                When(canceled=True, then=Value('c')),
                default=F('order__status'),
            )
        )
        .values('product', 'variation', 'status')
        .annotate(cnt=Count('id'), price=Sum('price'), tax_value=Sum('tax_value'))
        .order_by()
    )

    states = {
        'unapproved': 'unapproved',
        'canceled': Order.STATUS_CANCELED,
        'paid': Order.STATUS_PAID,
        'pending': Order.STATUS_PENDING,
        'expired': Order.STATUS_EXPIRED,
    }
    num = {}
    for l, s in states.items():
        num[l] = {
            (p['product'], p['variation']): (
                p['cnt'],
                p['price'],
                p['price'] - p['tax_value'],
            )
            for p in counters
            if p['status'] == s
        }

    num['total'] = dictsum(num['pending'], num['paid'])

    for product in products:
        product.all_variations = list(product.variations.all())
        product.has_variations = len(product.all_variations) > 0
        product.num = {}
        if product.has_variations:
            for var in product.all_variations:
                variid = var.id
                var.num = {}
                for l in states.keys():
                    var.num[l] = num[l].get((product.id, variid), (0, 0, 0))
                var.num['total'] = num['total'].get((product.id, variid), (0, 0, 0))
            for l in states.keys():
                product.num[l] = tuplesum(var.num[l] for var in product.all_variations)
            product.num['total'] = tuplesum(var.num['total'] for var in product.all_variations)
        else:
            for l in states.keys():
                product.num[l] = num[l].get((product.id, None), (0, 0, 0))
            product.num['total'] = num['total'].get((product.id, None), (0, 0, 0))

    nonecat = ProductCategory(name=_('Uncategorized'))
    # Regroup those by category
    products_by_category = sorted(
        [
            # a group is a tuple of a category and a list of products
            (
                cat if cat is not None else nonecat,
                [i for i in products if i.category == cat],
            )
            for cat in set([i.category for i in products])
            # insert categories into a set for uniqueness
            # a set is unsorted, so sort again by category
        ],
        key=lambda group: (group[0].position, group[0].id)
        if (group[0] is not None and group[0].id is not None)
        else (0, 0),
    )

    for c in products_by_category:
        c[0].num = {}
        for l in states.keys():
            c[0].num[l] = tuplesum(product.num[l] for product in c[1])
        c[0].num['total'] = tuplesum(product.num['total'] for product in c[1])

    # Payment fees
    payment_cat_obj = DummyObject()
    payment_cat_obj.name = _('Fees')
    payment_products = []

    if not subevent and fees:
        qs = OrderFee.all.filter(order__event=event).annotate(
            status=Case(
                When(
                    order__status='n',
                    order__require_approval=True,
                    then=Value('unapproved'),
                ),
                When(canceled=True, then=Value('c')),
                default=F('order__status'),
            )
        )
        if date_filter == 'order_date':
            if date_from:
                qs = qs.filter(order__datetime__gte=date_from)
            if date_until:
                qs = qs.filter(order__datetime__lt=date_until)
        elif date_filter == 'last_payment_date':
            qs = qs.annotate(payment_date=Subquery(p_date, output_field=DateTimeField()))
            if date_from:
                qs = qs.filter(payment_date__gte=date_from)
            if date_until:
                qs = qs.filter(payment_date__lt=date_until)
        counters = (
            qs.values('fee_type', 'internal_type', 'status')
            .annotate(cnt=Count('id'), value=Sum('value'), tax_value=Sum('tax_value'))
            .order_by()
        )

        for l, s in states.products():
            num[l] = {
                (o['fee_type'], o['internal_type']): (
                    o['cnt'],
                    o['value'],
                    o['value'] - o['tax_value'],
                )
                for o in counters
                if o['status'] == s
            }
        num['total'] = dictsum(num['pending'], num['paid'])

        provider_names = {k: v.verbose_name for k, v in event.get_payment_providers().items()}
        names = dict(OrderFee.FEE_TYPES)

        for pprov, total in sorted(num['total'].items(), key=lambda i: i[0]):
            ppobj = DummyObject()
            if pprov[0] == OrderFee.FEE_TYPE_PAYMENT:
                ppobj.name = '{} - {}'.format(names[pprov[0]], provider_names.get(pprov[1], pprov[1]))
            else:
                name = pprov[1]
                for r, resp in order_fee_type_name.send(sender=event, fee_type=pprov[0], internal_type=pprov[1]):
                    if resp:
                        name = resp
                        break

                ppobj.name = '{} - {}'.format(names[pprov[0]], name)
            ppobj.provider = pprov[1]
            ppobj.has_variations = False
            ppobj.num = {}
            for l in states.keys():
                ppobj.num[l] = num[l].get(pprov, (0, 0, 0))
            ppobj.num['total'] = total
            payment_products.append(ppobj)

        payment_cat_obj.num = {}
        for l in states.keys():
            payment_cat_obj.num[l] = (
                Dontsum(''),
                sum(i.num[l][1] for i in payment_products),
                sum(i.num[l][2] for i in payment_products),
            )
        payment_cat_obj.num['total'] = (
            Dontsum(''),
            sum(i.num['total'][1] for i in payment_products),
            sum(i.num['total'][2] for i in payment_products),
        )
        payment_cat = (payment_cat_obj, payment_products)
        any_payment = any(payment_cat_obj.num[s][1] for s in states.keys())
        if any_payment:
            products_by_category.append(payment_cat)

    total = {'num': {'total': tuplesum(c.num['total'] for c, i in products_by_category)}}
    for l in states.keys():
        total['num'][l] = tuplesum(c.num[l] for c, i in products_by_category)

    return products_by_category, total
