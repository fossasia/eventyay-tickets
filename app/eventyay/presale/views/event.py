import calendar
import datetime as dt
import importlib.util
import json
import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from urllib.parse import urlparse, urlunparse

import isoweek
import jwt
from zoneinfo import ZoneInfo
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db.models import (
    Count,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Value,
)
from django.db.models.expressions import OrderBy
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.formats import get_format
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django_scopes import scope

from eventyay.agenda.views.utils import (
    build_landing_featured_speakers_widget_schedule,
    build_featured_only_schedule_data_from_profiles,
    load_public_featured_speaker_profiles,
    serialize_widget_schedule_data,
)
from eventyay.base.channels import get_all_sales_channels
from eventyay.base.meetup import ensure_video_credentials, get_rsvp_product_and_quota, is_meetup_event
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.models import (
    Order,
    OrderPosition,
    ProductVariation,
    Quota,
    SeatCategoryMapping,
    User,
    Voucher,
)
from eventyay.base.models.event import SubEvent
from eventyay.base.models.product import (
    ProductBundle,
    ProductMetaValue,
    SubEventProduct,
    SubEventProductVariation,
)
from eventyay.base.services.geo import resolve_venue_map_coordinates
from eventyay.base.services.quotas import QuotaAvailability
from eventyay.common.views.helpers import login_redirect_with_next, redirect_or_json_redirect
from eventyay.helpers.compat import date_fromisocalendar
from eventyay.helpers.formats.en.formats import WEEK_FORMAT
from eventyay.multidomain.urlreverse import eventreverse
from eventyay.presale.ical import get_ical
from eventyay.presale.signals import product_description
from eventyay.presale.views.meetup import (
    MEETUP_RSVP_SESSION_KEY,
    RSVP_ORDER_STATUSES,
    GuestRsvpForm,
    has_rsvp_order,
)
from eventyay.presale.views.organizer import (
    EventListMixin,
    add_subevents_for_days,
    days_for_template,
    filter_qs_by_attr,
    weeks_for_template,
)
from eventyay.talk_rules.agenda import public_speakers_list_available

from ...eventyay_common.utils import encode_email
from . import (
    CartMixin,
    EventViewMixin,
    allow_frame_if_namespaced,
    get_cart,
    iframe_entry_view_wrapper,
)


SessionStore = import_module(settings.SESSION_ENGINE).SessionStore

logger = logging.getLogger(__name__)


def product_group_by_category(products):
    return sorted(
        [
            # a group is a tuple of a category and a list of products
            (cat, [i for i in products if i.category == cat])
            for cat in set([i.category for i in products])
            # insert categories into a set for uniqueness
            # a set is unsorted, so sort again by category
        ],
        key=lambda group: (group[0].position, group[0].id)
        if (group[0] is not None and group[0].id is not None)
        else (0, 0),
    )


def get_grouped_products(
    event,
    subevent=None,
    voucher=None,
    channel='web',
    require_seat=0,
    base_qs=None,
    allow_addons=False,
    quota_cache=None,
    filter_products=None,
    filter_categories=None,
):
    base_qs_set = base_qs is not None
    base_qs = base_qs if base_qs is not None else event.products

    requires_seat = Exists(SeatCategoryMapping.objects.filter(product_id=OuterRef('pk'), subevent=subevent))
    if not event.settings.seating_choice:
        requires_seat = Value(0, output_field=IntegerField())

    products = (
        base_qs.using(settings.DATABASE_REPLICA)
        .filter_available(channel=channel, voucher=voucher, allow_addons=allow_addons)
        .select_related(
            'category',
            'tax_rule',  # for re-grouping
            'hidden_if_available',
        )
        .prefetch_related(
            Prefetch(
                'quotas',
                to_attr='_subevent_quotas',
                queryset=event.quotas.using(settings.DATABASE_REPLICA).filter(subevent=subevent),
            ),
            Prefetch(
                'bundles',
                queryset=ProductBundle.objects.using(settings.DATABASE_REPLICA).prefetch_related(
                    Prefetch(
                        'bundled_product',
                        queryset=event.products.using(settings.DATABASE_REPLICA)
                        .select_related('tax_rule')
                        .prefetch_related(
                            Prefetch(
                                'quotas',
                                to_attr='_subevent_quotas',
                                queryset=event.quotas.using(settings.DATABASE_REPLICA).filter(subevent=subevent),
                            ),
                        ),
                    ),
                    Prefetch(
                        'bundled_variation',
                        queryset=ProductVariation.objects.using(settings.DATABASE_REPLICA)
                        .select_related('product', 'product__tax_rule')
                        .filter(product__event=event)
                        .prefetch_related(
                            Prefetch(
                                'quotas',
                                to_attr='_subevent_quotas',
                                queryset=event.quotas.using(settings.DATABASE_REPLICA).filter(subevent=subevent),
                            ),
                        ),
                    ),
                ),
            ),
            Prefetch(
                'variations',
                to_attr='available_variations',
                queryset=ProductVariation.objects.using(settings.DATABASE_REPLICA)
                .annotate(
                    subevent_disabled=Exists(
                        SubEventProductVariation.objects.filter(
                            variation_id=OuterRef('pk'),
                            subevent=subevent,
                            disabled=True,
                        )
                    ),
                )
                .filter(active=True, quotas__isnull=False, subevent_disabled=False)
                .prefetch_related(
                    Prefetch(
                        'quotas',
                        to_attr='_subevent_quotas',
                        queryset=event.quotas.using(settings.DATABASE_REPLICA).filter(subevent=subevent),
                    )
                )
                .distinct(),
            ),
        )
        .annotate(
            quotac=Count('quotas'),
            has_variations=Count('variations'),
            subevent_disabled=Exists(
                SubEventProduct.objects.filter(
                    product_id=OuterRef('pk'),
                    subevent=subevent,
                    disabled=True,
                )
            ),
            requires_seat=requires_seat,
        )
        .filter(
            quotac__gt=0,
            subevent_disabled=False,
        )
        .order_by('category__position', 'category_id', 'position', 'name')
    )
    if require_seat:
        products = products.filter(requires_seat__gt=0)
    else:
        products = products.filter(requires_seat=0)

    if filter_products:
        products = products.filter(pk__in=[a for a in filter_products if a.isdigit()])
    if filter_categories:
        products = products.filter(category_id__in=[a for a in filter_categories if a.isdigit()])

    display_add_to_cart = False
    quota_cache_key = f'product_quota_cache:{subevent.id if subevent else 0}:{channel}:{bool(require_seat)}'
    quota_cache = quota_cache or event.cache.get(quota_cache_key) or {}
    quota_cache_existed = bool(quota_cache)

    if subevent:
        product_price_override = subevent.product_price_overrides
        var_price_override = subevent.var_price_overrides
    else:
        product_price_override = {}
        var_price_override = {}

    restrict_vars = set()
    if voucher and voucher.quota_id:
        # If a voucher is set to a specific quota, we need to filter out on that level
        restrict_vars = set(voucher.quota.variations.all())

    quotas_to_compute = []
    for product in products:
        if product.has_variations:
            for v in product.available_variations:
                for q in v._subevent_quotas:
                    if q.pk not in quota_cache:
                        quotas_to_compute.append(q)
        else:
            for q in product._subevent_quotas:
                if q.pk not in quota_cache:
                    quotas_to_compute.append(q)

    if quotas_to_compute:
        qa = QuotaAvailability()
        qa.queue(*quotas_to_compute)
        qa.compute()
        quota_cache.update({q.pk: r for q, r in qa.results.items()})

    product_ids = [p.pk for p in products]
    limit_one_per_user_product_ids = set(
        ProductMetaValue.objects.filter(
            product_id__in=product_ids,
            property__event=event,
            property__name='limit_one_per_user',
        ).values_list('product_id', flat=True)
    )

    for product in products:
        if voucher and voucher.product_id and voucher.variation_id:
            # Restrict variations if the voucher only allows one
            product.available_variations = [v for v in product.available_variations if v.pk == voucher.variation_id]

        if get_all_sales_channels()[channel].unlimited_products_per_order:
            max_per_order = sys.maxsize
        else:
            max_per_order = product.max_per_order or (int(GlobalSettingsObject().settings.get('max_products_per_order', default=0) or 0) or sys.maxsize)
        product.effective_max_per_order = None if max_per_order == sys.maxsize else max_per_order

        if product.hidden_if_available:
            q = product.hidden_if_available.availability(_cache=quota_cache)
            if q[0] == Quota.AVAILABILITY_OK:
                product._remove = True
                continue

        product.description = str(product.description)
        for recv, resp in product_description.send(sender=event, product=product, variation=None):
            if resp:
                product.description += ('<br/>' if product.description else '') + resp

        if not product.has_variations:
            product._remove = False
            if not bool(product._subevent_quotas):
                product._remove = True
                continue

            if voucher and (voucher.allow_ignore_quota or voucher.block_quota):
                product.cached_availability = (
                    Quota.AVAILABILITY_OK,
                    voucher.max_usages - voucher.redeemed,
                )
            else:
                product.cached_availability = list(
                    product.check_quotas(subevent=subevent, _cache=quota_cache, include_bundled=True)
                )

            if event.settings.hide_sold_out and product.cached_availability[0] < Quota.AVAILABILITY_RESERVED:
                product._remove = True
                continue

            product.limit_one_per_user = product.pk in limit_one_per_user_product_ids

            product.order_max = min(
                product.cached_availability[1] if product.cached_availability[1] is not None else sys.maxsize,
                max_per_order,
            )

            if product.limit_one_per_user:
                product.order_max = min(product.order_max, 1)
                if product.min_per_order and product.min_per_order > 1:
                    product.min_per_order = 1

            original_price = product_price_override.get(product.pk, product.default_price)
            if voucher:
                price = voucher.calculate_price(original_price)
            else:
                price = original_price

            product.display_price = product.tax(price, currency=event.currency, include_bundled=True)

            if price != original_price:
                product.original_price = product.tax(original_price, currency=event.currency, include_bundled=True)
            else:
                product.original_price = (
                    product.tax(
                        product.original_price,
                        currency=event.currency,
                        include_bundled=True,
                        base_price_is='net' if event.settings.display_net_prices else 'gross',
                    )  # backwards-compat
                    if product.original_price
                    else None
                )

            display_add_to_cart = display_add_to_cart or product.order_max > 0
        else:
            product.limit_one_per_user = product.pk in limit_one_per_user_product_ids
            product.single_variation_selection = (
                max_per_order == 1
                or product.limit_one_per_user
            )

            if product.limit_one_per_user and product.min_per_order and product.min_per_order > 1:
                product.min_per_order = 1

            for var in product.available_variations:
                var.description = str(var.description)
                for recv, resp in product_description.send(sender=event, product=product, variation=var):
                    if resp:
                        var.description += ('<br/>' if var.description else '') + resp

                if voucher and (voucher.allow_ignore_quota or voucher.block_quota):
                    var.cached_availability = (
                        Quota.AVAILABILITY_OK,
                        voucher.max_usages - voucher.redeemed,
                    )
                else:
                    var.cached_availability = list(
                        var.check_quotas(subevent=subevent, _cache=quota_cache, include_bundled=True)
                    )

                var.order_max = min(
                    var.cached_availability[1] if var.cached_availability[1] is not None else sys.maxsize,
                    max_per_order,
                )

                if product.limit_one_per_user:
                    var.order_max = min(var.order_max, 1)
                    if hasattr(var, 'min_per_order') and var.min_per_order and var.min_per_order > 1:
                        var.min_per_order = 1

                original_price = var_price_override.get(var.pk, var.price)
                if voucher:
                    price = voucher.calculate_price(original_price)
                else:
                    price = original_price

                var.display_price = var.tax(price, currency=event.currency, include_bundled=True)

                if price != original_price:
                    var.original_price = var.tax(original_price, currency=event.currency, include_bundled=True)
                else:
                    var.original_price = (
                        (
                            var.tax(
                                var.original_price or product.original_price,
                                currency=event.currency,
                                include_bundled=True,
                                base_price_is='net' if event.settings.display_net_prices else 'gross',
                            )  # backwards-compat
                        )
                        if var.original_price or product.original_price
                        else None
                    )

                display_add_to_cart = display_add_to_cart or var.order_max > 0

            product.original_price = (
                product.tax(
                    product.original_price,
                    currency=event.currency,
                    include_bundled=True,
                    base_price_is='net' if event.settings.display_net_prices else 'gross',
                )  # backwards-compat
                if product.original_price
                else None
            )

            product.available_variations = [
                v
                for v in product.available_variations
                if v._subevent_quotas and (not voucher or not voucher.quota_id or v in restrict_vars)
            ]

            if event.settings.hide_sold_out:
                product.available_variations = [
                    v for v in product.available_variations if v.cached_availability[0] >= Quota.AVAILABILITY_RESERVED
                ]

            if voucher and voucher.variation_id:
                product.available_variations = [v for v in product.available_variations if v.pk == voucher.variation_id]

            if len(product.available_variations) > 0:
                product.min_price = min(
                    [
                        v.display_price.net if event.settings.display_net_prices else v.display_price.gross
                        for v in product.available_variations
                    ]
                )
                product.max_price = max(
                    [
                        v.display_price.net if event.settings.display_net_prices else v.display_price.gross
                        for v in product.available_variations
                    ]
                )

            product._remove = not bool(product.available_variations)

    if (
        not quota_cache_existed
        and not voucher
        and not allow_addons
        and not base_qs_set
        and not filter_products
        and not filter_categories
    ):
        event.cache.set(quota_cache_key, quota_cache, 5)
    products = [
        product
        for product in products
        if (len(product.available_variations) > 0 or not product.has_variations) and not product._remove
    ]
    return products, display_add_to_cart


def event_has_redeemable_voucher_products(event, subevent=None, channel='web'):
    """
    Return whether at least one active voucher can still be used to purchase
    an available product.
    """
    cache_key = f'event_has_redeemable_voucher_products:{event.pk}:{subevent.id if subevent else 0}:{channel}'
    res = event.cache.get(cache_key)
    if res is not None:
        return res

    active_vouchers = event.vouchers.filter(
        redeemed__lt=F('max_usages')
    ).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=now())
    )
    if not active_vouchers.exists():
        event.cache.set(cache_key, False, 10)
        return False

    if event.has_subevents and subevent is None:
        subevents_to_check = list(event.subevents.filter(active=True))
    else:
        subevents_to_check = [subevent]

    if not subevents_to_check:
        event.cache.set(cache_key, False, 10)
        return False

    if event.has_subevents:
        vouchers = list(active_vouchers.filter(
            Q(subevent__in=subevents_to_check) | Q(subevent__isnull=True)
        ).select_related('product', 'quota'))
    else:
        vouchers = list(active_vouchers.filter(
            Q(subevent__isnull=True)
        ).select_related('product', 'quota'))

    if not vouchers:
        event.cache.set(cache_key, False, 10)
        return False

    products_qs = event.products.filter(
        active=True,
        require_bundling=False
    ).filter(
        Q(available_from__isnull=True) | Q(available_from__lte=now())
    ).filter(
        Q(available_until__isnull=True) | Q(available_until__gte=now())
    ).filter(
        sales_channels__contains=channel
    ).filter(
        Q(category__isnull=True) | Q(category__is_addon=False)
    )

    products = list(products_qs.prefetch_related('quotas', 'variations'))
    if not products:
        event.cache.set(cache_key, False, 10)
        return False

    variations_qs = ProductVariation.objects.filter(
        product__event=event,
        active=True
    ).prefetch_related('quotas')

    variations_list = list(variations_qs)
    variations_by_product = defaultdict(list)
    for var in variations_list:
        variations_by_product[var.product_id].append(var)

    disabled_products = set()
    disabled_variations = set()
    if event.has_subevents:
        se_ids = [se.id for se in subevents_to_check if se]
        if se_ids:
            disabled_products = set(
                SubEventProduct.objects.filter(
                    subevent_id__in=se_ids,
                    disabled=True
                ).values_list('subevent_id', 'product_id')
            )
            disabled_variations = set(
                SubEventProductVariation.objects.filter(
                    subevent_id__in=se_ids,
                    disabled=True
                ).values_list('subevent_id', 'variation_id')
            )

    all_quotas = set()
    items_to_check = []

    for se in subevents_to_check:
        se_id = se.id if se else None
        se_vouchers = [v for v in vouchers if v.subevent_id is None or v.subevent_id == se_id]
        
        if not se_vouchers:
            continue
            
        for p in products:
            if (se_id, p.pk) in disabled_products:
                continue
                
            if p.has_variations:
                for var in variations_by_product.get(p.pk, []):
                    if (se_id, var.pk) in disabled_variations:
                        continue
                    
                    items_to_check.append((se, se_vouchers, p, var))
                    for q in var.quotas.all():
                        if q.subevent_id == se_id:
                            all_quotas.add(q)
            else:
                items_to_check.append((se, se_vouchers, p, None))
                for q in p.quotas.all():
                    if q.subevent_id == se_id:
                        all_quotas.add(q)

    if not items_to_check:
        event.cache.set(cache_key, False, 10)
        return False

    quota_cache = {}
    if all_quotas:
        qa = QuotaAvailability()
        qa.queue(*all_quotas)
        qa.compute()
        quota_cache = {q.pk: r for q, r in qa.results.items()}

    def voucher_applies_to(v, p, var=None):
        if v.quota_id:
            if var:
                return any(q.pk == v.quota_id for q in var.quotas.all())
            return any(q.pk == v.quota_id for q in p.quotas.all())
        if v.product_id and not v.variation_id:
            return v.product_id == p.pk
        if v.product_id:
            return v.product_id == p.pk and var and v.variation_id == var.pk
        return True

    def check_item_avail(quotas, se, ignore_quota=False):
        if ignore_quota:
            return True
        se_quotas = [q for q in quotas if q.subevent_id == (se.id if se else None)]
        if not se_quotas:
            return False
        for q in se_quotas:
            res = quota_cache.get(q.pk)
            if not res:
                return False
            if event.settings.hide_sold_out and res[0] < Quota.AVAILABILITY_RESERVED:
                return False
            if res[1] is not None and res[1] <= 0:
                return False
            if res[0] == Quota.AVAILABILITY_GONE:
                return False
        return True

    for se, se_vouchers, p, var in items_to_check:
        quotas = var.quotas.all() if var else p.quotas.all()
        is_normally_available = check_item_avail(quotas, se, False)
        
        for v in se_vouchers:
            if voucher_applies_to(v, p, var):
                if p.hide_without_voucher and not v.show_hidden_products:
                    continue
                if is_normally_available or v.allow_ignore_quota or v.block_quota:
                    event.cache.set(cache_key, True, 10)
                    return True

    event.cache.set(cache_key, False, 10)
    return False
@method_decorator(allow_frame_if_namespaced, 'dispatch')
@method_decorator(iframe_entry_view_wrapper, 'dispatch')
class EventIndex(EventViewMixin, EventListMixin, CartMixin, TemplateView):
    template_name = 'pretixpresale/event/index.html'

    def get_template_names(self):
        if is_meetup_event(self.request.event):
            return ['pretixpresale/event/meetup_index.html']
        return [self.template_name]

    def get(self, request, *args, **kwargs):
        from eventyay.presale.views.cart import get_or_create_cart_id

        self.subevent = None
        if request.GET.get('src', '') == 'widget' and 'take_cart_id' in request.GET:
            # User has clicked "Open in a new tab" link in widget
            get_or_create_cart_id(request)
            redirect_url = eventreverse(request.event, 'presale:event.index', kwargs=kwargs)
            logger.info('Redirecting to %s...', redirect_url)
            return redirect(redirect_url)
        elif request.GET.get('iframe', '') == '1' and 'take_cart_id' in request.GET:
            # Widget just opened, a cart already exists. Let's to a stupid redirect to check if cookies are disabled
            get_or_create_cart_id(request)
            redirect_url = eventreverse(request.event, 'presale:event.index', kwargs=kwargs) + '?require_cookie=true&cart_id={}'.format(request.GET.get('take_cart_id'))
            logger.info('Redirecting to %s...', redirect_url)
            return redirect(redirect_url)
        elif request.GET.get('iframe', '') == '1' and len(self.request.GET.get('widget_data', '{}')) > 3:
            # We've been passed data from a widget, we need to create a cart session to store it.
            get_or_create_cart_id(request)
        elif 'require_cookie' in request.GET and settings.SESSION_COOKIE_NAME not in request.COOKIES:
            # Cookies are in fact not supported
            r = render(
                request,
                'pretixpresale/event/cookies.html',
                {
                    'url': eventreverse(
                        request.event,
                        'presale:event.index',
                        kwargs={'cart_namespace': kwargs.get('cart_namespace') or ''},
                    )
                    + (
                        '?src=widget&take_cart_id={}'.format(request.GET.get('cart_id'))
                        if 'cart_id' in request.GET
                        else ''
                    )
                },
            )
            r._csp_ignore = True
            return r

        if request.sales_channel.identifier not in request.event.sales_channels:
            raise Http404(_('Tickets for this event cannot be purchased on this sales channel.'))

        if request.event.has_subevents:
            if 'subevent' in kwargs:
                self.subevent = (
                    request.event.subevents.using(settings.DATABASE_REPLICA)
                    .filter(pk=kwargs['subevent'], active=True)
                    .first()
                )
                if not self.subevent:
                    raise Http404()
                return super().get(request, *args, **kwargs)
            else:
                return super().get(request, *args, **kwargs)
        else:
            if 'subevent' in kwargs:
                redirect_url = self.get_index_url()
                logger.info('Redirecting to %s...', redirect_url)
                return redirect(redirect_url)
            else:
                return super().get(request, *args, **kwargs)

    def get_meetup_context(self):
        event = self.request.event
        if not is_meetup_event(event):
            return {'is_meetup_event': False, 'attendee_already_registered': False, 'rsvp_registration_closed': False}

        if self.request.user.is_authenticated:
            already_registered = has_rsvp_order(event, self.request.user.email)
        else:
            order_code = self.request.session.get(MEETUP_RSVP_SESSION_KEY.format(event.pk))
            if order_code:
                with scope(organizer=event.organizer):
                    already_registered = event.orders.filter(code=order_code, status__in=RSVP_ORDER_STATUSES).exists()
            else:
                already_registered = False

        with scope(organizer=event.organizer):
            attendee_count = event.orders.filter(status__in=RSVP_ORDER_STATUSES).count()
            preview_positions = list(
                OrderPosition.objects.filter(
                    order__event=event,
                    order__status__in=RSVP_ORDER_STATUSES,
                )
                .select_related('order')
                .order_by('order__datetime')
                [:6]
            )
            emails = {
                (pos.attendee_email or pos.order.email).strip().lower()
                for pos in preview_positions
                if (pos.attendee_email or pos.order.email)
            }
            user_avatars = {}
            if emails:
                users = (
                    User.objects.filter(email__in=emails, event__isnull=True)
                    .only('id', 'email', 'profile_picture', 'profile_picture_thumbnail', 'profile_picture_thumbnail_tiny')
                )
                for u in users:
                    avatar_url = u.get_profile_picture_url(event=event, thumbnail='default') or u.get_profile_picture_url(event=event)
                    if avatar_url:
                        user_avatars[u.email.lower()] = avatar_url

            attendees_preview = [
                {
                    'name': pos.attendee_name,
                    'avatar_url': user_avatars.get((pos.attendee_email or pos.order.email or '').strip().lower()),
                }
                for pos in preview_positions
                if pos.attendee_name
            ]

        rsvp_registration_closed = False
        product, quota = get_rsvp_product_and_quota(event)
        if quota and quota.size is not None:
            with scope(organizer=event.organizer):
                avail, count = quota.availability()
                rsvp_registration_closed = avail != Quota.AVAILABILITY_OK

        registration_fee = product.default_price if product else Decimal('0.00')

        return {
            'is_meetup_event': True,
            'attendee_already_registered': already_registered,
            'rsvp_guest_form': getattr(self.request, '_rsvp_guest_form', None) or GuestRsvpForm(),
            'meetup_attendee_count': attendee_count,
            'meetup_attendees_preview': attendees_preview,
            'rsvp_registration_closed': rsvp_registration_closed,
            'guest_checkout_allowed': not event.settings.require_registered_account_for_tickets,
            'meetup_registration_fee': registration_fee or Decimal('0.00'),
            'stripe_publishable_key': event.settings.get('payment_stripe_publishable_key', ''),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(self.get_meetup_context())

        # Show voucher option only if redeemable products exist for active vouchers
        vouchers_exist = event_has_redeemable_voucher_products(
            self.request.event,
            self.subevent,
            channel=self.request.sales_channel.identifier,
        )
        context['show_vouchers'] = context['vouchers_exist'] = vouchers_exist

        if not self.request.event.has_subevents or self.subevent:
            # Fetch all products
            products, display_add_to_cart = get_grouped_products(
                self.request.event,
                self.subevent,
                filter_products=self.request.GET.getlist('product'),
                filter_categories=self.request.GET.getlist('category'),
                channel=self.request.sales_channel.identifier,
            )
            context['productnum'] = len(products)
            context['allfree'] = all(
                product.display_price.gross == Decimal('0.00') for product in products if not product.has_variations
            ) and all(
                all(var.display_price.gross == Decimal('0.00') for var in product.available_variations)
                for product in products
                if product.has_variations
            )

            # Regroup those by category
            context['products_by_category'] = product_group_by_category(products)
            context['display_add_to_cart'] = display_add_to_cart

        context['ev'] = self.subevent or self.request.event
        context['venue_map_location'] = resolve_venue_map_coordinates(
            context['ev'],
            allow_remote_geocoding=False,
        )
        context['subevent'] = self.subevent
        context['cart'] = self.get_cart()
        context['has_addon_choices'] = any(cp.has_addon_choices for cp in get_cart(self.request))
        if self.subevent:
            context['frontpage_text'] = self.subevent.frontpage_text
        else:
            context['frontpage_text'] = self.request.event.settings.frontpage_text

        if self.request.event.has_subevents:
            context.update(self._subevent_list_context())

        context['can_view_tickets'] = self.request.event.user_can_view_tickets(
            self.request.user,
            request=self.request,
        )
        context['show_cart'] = (
            context['can_view_tickets']
            and context['cart']['positions']
            and (self.request.event.has_subevents or self.request.event.presale_is_running)
        )
        if self.request.event.settings.redirect_to_checkout_directly:
            context['cart_redirect'] = eventreverse(
                self.request.event,
                'presale:event.checkout.start',
                kwargs={'cart_namespace': kwargs.get('cart_namespace') or ''},
            )
            if context['cart_redirect'].startswith('https:'):
                context['cart_redirect'] = '/' + context['cart_redirect'].split('/', 3)[3]
        else:
            context['cart_redirect'] = self.request.get_full_path()

        # Get event_name in language code
        event_name_data = self.request.event.name.data

        if isinstance(event_name_data, dict):
            # If event_name_data is a dictionary, try to get the name based on LANGUAGE_CODE
            event_name = event_name_data.get(self.request.LANGUAGE_CODE)

            if event_name is None:
                # If event_name is not available in the language code, get event name in English
                event_name = event_name_data.get('en')

            if event_name is None and len(event_name_data) > 0:
                # If event_name is not available in English, get the first available event name
                event_name = next(iter(event_name_data.values()))
        else:
            # If event_name_data is a string, use it directly
            event_name = event_name_data

        context['event_name'] = event_name
        context['guest_checkout_allowed'] = not self.request.event.settings.require_registered_account_for_tickets
        context['featured_speakers'] = []
        context['featured_speakers_widget_schedule'] = None
        context['featured_speakers_widget_schedule_json'] = ''
        context['featured_speakers_list_public'] = False

        event = self.request.event
        featured_speaker_profiles = load_public_featured_speaker_profiles(
            self.request.user,
            event,
        )

        if featured_speaker_profiles:
            context['featured_speakers'] = featured_speaker_profiles
            schedule_data = build_landing_featured_speakers_widget_schedule(
                event,
                self.request.user,
                featured_speaker_profiles,
            )
            if not schedule_data:
                schedule_data = build_featured_only_schedule_data_from_profiles(
                    event,
                    featured_speaker_profiles,
                    speakers_list_public=public_speakers_list_available(AnonymousUser(), event),
                )
            if schedule_data:
                context['featured_speakers_widget_schedule'] = schedule_data
                context['featured_speakers_list_public'] = schedule_data.get('speakers_list_public', False)
                context['featured_speakers_widget_schedule_json'] = serialize_widget_schedule_data(
                    schedule_data,
                    event=event,
                )

        return context

    def _subevent_list_context(self):
        voucher = None
        if self.request.GET.get('voucher'):
            try:
                voucher = Voucher.objects.get(
                    code__iexact=self.request.GET.get('voucher'),
                    event=self.request.event,
                )
            except Voucher.DoesNotExist:
                pass

        context = {}
        context['list_type'] = self.request.GET.get('style', self.request.event.settings.event_list_type)
        if (
            context['list_type'] not in ('calendar', 'week')
            and self.request.event.subevents.filter(date_from__gt=now()).count() > 50
        ):
            if self.request.event.settings.event_list_type not in ('calendar', 'week'):
                self.request.event.settings.event_list_type = 'calendar'
            context['list_type'] = 'calendar'

        if context['list_type'] == 'calendar':
            self._set_month_year()
            tz = ZoneInfo(self.request.event.settings.timezone)
            _, ndays = calendar.monthrange(self.year, self.month)
            before = datetime(self.year, self.month, 1, 0, 0, 0, tzinfo=tz) - timedelta(days=1)
            after = datetime(self.year, self.month, ndays, 0, 0, 0, tzinfo=tz) + timedelta(days=1)

            context['date'] = date(self.year, self.month, 1)
            context['before'] = before
            context['after'] = after

            ebd = defaultdict(list)
            add_subevents_for_days(
                filter_qs_by_attr(
                    self.request.event.subevents_annotated(self.request.sales_channel.identifier).using(
                        settings.DATABASE_REPLICA
                    ),
                    self.request,
                ),
                before,
                after,
                ebd,
                set(),
                self.request.event,
                self.kwargs.get('cart_namespace'),
                voucher,
            )

            context['show_names'] = (
                ebd.get('_subevents_different_names', False)
                or sum(len(i) for i in ebd.values() if isinstance(i, list)) < 2
            )
            context['weeks'] = weeks_for_template(ebd, self.year, self.month)
            context['months'] = [date(self.year, i + 1, 1) for i in range(12)]
            context['years'] = range(now().year - 2, now().year + 3)
        elif context['list_type'] == 'week':
            self._set_week_year()
            tz = ZoneInfo(self.request.event.settings.timezone)
            week = isoweek.Week(self.year, self.week)
            before = datetime(
                week.monday().year,
                week.monday().month,
                week.monday().day,
                0,
                0,
                0,
                tzinfo=tz,
            ) - timedelta(days=1)
            after = datetime(
                week.sunday().year,
                week.sunday().month,
                week.sunday().day,
                0,
                0,
                0,
                tzinfo=tz,
            ) + timedelta(days=1)

            context['date'] = week.monday()
            context['before'] = before
            context['after'] = after

            ebd = defaultdict(list)
            add_subevents_for_days(
                filter_qs_by_attr(
                    self.request.event.subevents_annotated(self.request.sales_channel.identifier).using(
                        settings.DATABASE_REPLICA
                    ),
                    self.request,
                ),
                before,
                after,
                ebd,
                set(),
                self.request.event,
                self.kwargs.get('cart_namespace'),
                voucher,
            )

            context['show_names'] = (
                ebd.get('_subevents_different_names', False)
                or sum(len(i) for i in ebd.values() if isinstance(i, list)) < 2
            )
            context['days'] = days_for_template(ebd, week)
            context['weeks'] = [
                (
                    date_fromisocalendar(self.year, i + 1, 1),
                    date_fromisocalendar(self.year, i + 1, 7),
                )
                for i in range(53 if date(self.year, 12, 31).isocalendar()[1] == 53 else 52)
            ]
            context['years'] = range(now().year - 2, now().year + 3)
            context['week_format'] = get_format('WEEK_FORMAT')
            if context['week_format'] == 'WEEK_FORMAT':
                context['week_format'] = WEEK_FORMAT
        else:
            context['subevent_list'] = self.request.event.subevents_sorted(
                filter_qs_by_attr(
                    self.request.event.subevents_annotated(self.request.sales_channel.identifier).using(
                        settings.DATABASE_REPLICA
                    ),
                    self.request,
                )
            )
            if self.request.event.settings.event_list_available_only and not voucher:
                context['subevent_list'] = [
                    se
                    for se in context['subevent_list']
                    if not se.presale_has_ended and se.best_availability_state >= Quota.AVAILABILITY_RESERVED
                ]
        return context


@method_decorator(allow_frame_if_namespaced, 'dispatch')
@method_decorator(iframe_entry_view_wrapper, 'dispatch')
class SeatingPlanView(EventViewMixin, TemplateView):
    template_name = 'pretixpresale/event/seatingplan.html'

    def get(self, request, *args, **kwargs):
        from eventyay.presale.views.cart import get_or_create_cart_id

        self.subevent = None
        if request.GET.get('src', '') == 'widget' and 'take_cart_id' in request.GET:
            # User has clicked "Open in a new tab" link in widget
            get_or_create_cart_id(request)
            redirect_url = eventreverse(request.event, 'presale:event.seatingplan', kwargs=kwargs)
            logger.info('Redirecting to %s...', redirect_url)
            return redirect(redirect_url)
        elif request.GET.get('iframe', '') == '1' and 'take_cart_id' in request.GET:
            # Widget just opened, a cart already exists. Let's to a stupid redirect to check if cookies are disabled
            get_or_create_cart_id(request)
            redirect_url = eventreverse(request.event, 'presale:event.seatingplan', kwargs=kwargs) + '?require_cookie=true&cart_id={}'.format(request.GET.get('take_cart_id'))
            logger.info('Redirecting to %s...', redirect_url)
            return redirect(redirect_url)
        elif request.GET.get('iframe', '') == '1' and len(self.request.GET.get('widget_data', '{}')) > 3:
            # We've been passed data from a widget, we need to create a cart session to store it.
            get_or_create_cart_id(request)

        if request.event.has_subevents:
            if 'subevent' in kwargs:
                self.subevent = (
                    request.event.subevents.using(settings.DATABASE_REPLICA)
                    .filter(pk=kwargs['subevent'], active=True)
                    .first()
                )
                if not self.subevent or not self.subevent.seating_plan:
                    raise Http404()
                return super().get(request, *args, **kwargs)
            else:
                raise Http404()
        else:
            if 'subevent' in kwargs or not request.event.seating_plan:
                raise Http404()
            else:
                return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subevent'] = self.subevent
        context['cart_redirect'] = eventreverse(
            self.request.event,
            'presale:event.checkout.start',
            kwargs={'cart_namespace': kwargs.get('cart_namespace') or ''},
        )
        if context['cart_redirect'].startswith('https:'):
            context['cart_redirect'] = '/' + context['cart_redirect'].split('/', 3)[3]
        return context


class EventIcalDownload(EventViewMixin, View):
    def get(self, request, *args, **kwargs):
        if not self.request.event:
            raise Http404(_('Unknown event code or not authorized to access this event.'))

        subevent = None
        if request.event.has_subevents:
            if 'subevent' in kwargs:
                subevent = get_object_or_404(SubEvent, event=request.event, pk=kwargs['subevent'], active=True)
            else:
                raise Http404(pgettext_lazy('subevent', 'No date selected.'))
        else:
            if 'subevent' in kwargs:
                raise Http404(pgettext_lazy('subevent', 'Unknown date selected.'))

        event = self.request.event
        cal = get_ical([subevent or event])

        resp = HttpResponse(cal.serialize(), content_type='text/calendar')
        resp['Content-Disposition'] = 'attachment; filename="{}-{}-{}.ics"'.format(
            event.organizer.slug,
            event.slug,
            subevent.pk if subevent else '0',
        )
        return resp


class EventAuth(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        s = SessionStore(request.POST.get('session'))

        try:
            data = s.load()
        except:
            raise PermissionDenied(_('Please go back and try again.'))

        parent = data.get('pretix_event_access_{}'.format(request.event.pk))

        sparent = SessionStore(parent)
        try:
            parentdata = sparent.load()
        except:
            raise PermissionDenied(_('Please go back and try again.'))
        else:
            if 'event_access' not in parentdata:
                raise PermissionDenied(_('Please go back and try again.'))

        request.session['pretix_event_access_{}'.format(request.event.pk)] = parent
        redirect_url = eventreverse(request.event, 'presale:event.index')
        logger.info('Redirecting to %s...', redirect_url)
        return redirect(redirect_url)


@method_decorator(allow_frame_if_namespaced, 'dispatch')
@method_decorator(iframe_entry_view_wrapper, 'dispatch')
class JoinOnlineVideoView(EventViewMixin, View):
    def get(self, request, *args, **kwargs):
        event = self.request.event
        is_allowed, order_position, order = self.validate_access(request, *args, **kwargs)
        if not is_allowed:
            return HttpResponse(status=403, content='user_not_allowed')

        if is_meetup_event(event):
            ensure_video_credentials(event, request=request)

        if (
            not self.request.event.settings.venueless_url
            or not self.request.event.settings.venueless_issuer
            or not self.request.event.settings.venueless_audience
            or not self.request.event.settings.venueless_secret
        ):
            logger.error('Video Online configuration is not available for this event.')
            raise PermissionDenied(_('Please go back and try again.'))

        redirect_url = self.generate_token_url(request, order_position, order)
        logger.info('Redirecting to %s...', redirect_url)
        return redirect_or_json_redirect(request, redirect_url)

    def validate_access(self, request, *args, **kwargs):
        session_order_code = (
            request.session.get(MEETUP_RSVP_SESSION_KEY.format(self.request.event.pk))
            if is_meetup_event(self.request.event)
            else None
        )
        if not self.request.user.is_authenticated and not session_order_code:
            return False, None, None
        
        allowed_statuses = [Order.STATUS_PAID]
        if self.request.event.settings.venueless_allow_pending:
            allowed_statuses.append(Order.STATUS_PENDING)

        with scope(organizer=self.request.event.organizer):
            filters = Q(event=self.request.event) & Q(status__in=allowed_statuses)
            if self.request.user.is_authenticated:
                filters &= (
                    Q(email__iexact=self.request.user.email)
                    | Q(all_positions__attendee_email__iexact=self.request.user.email)
                )
            elif session_order_code:
                filters &= Q(code=session_order_code)
            else:
                return False, None, None

            order_list = list(
                Order.objects.filter(filters)
                .select_related('event')
                .prefetch_related(
                    'positions',
                    'positions__product',
                    'positions__product__category',
                    'positions__variation',
                    'positions__addons',
                    'positions__addons__product',
                    'positions__addons__variation',
                    'positions__answers',
                    'positions__answers__question',
                )
                .order_by('-datetime')
                .distinct()
            )
        # Check qs is empty
        if not order_list:
            # no paid order found
            return False, None, None

        if is_meetup_event(self.request.event):
            return True, None, order_list[0]
        list_allow_ticket_type = self.request.event.settings.venueless_products
        all_products_allowed = self.request.event.settings.venueless_all_products
        
        if not list_allow_ticket_type and not all_products_allowed:
            # no ticket allow to join
            return False, None, None
            
        for order in order_list:
            order_positions = list(order.positions.all())
            for order_position in order_positions:
                # If specific products are allowed, verify this position is one of them
                if not all_products_allowed and order_position.product_id not in list_allow_ticket_type:
                    continue
                    
                # We should prefer a position where the attendee email matches the user,
                # or if the user is the orderer, any valid position
                if (order_position.attendee_email and order_position.attendee_email.lower() == self.request.user.email.lower()) or \
                   (order.email and order.email.lower() == self.request.user.email.lower()):
                    return True, order_position, order
        
        return False, None, None

    def generate_token_url(self, request, order_position, order):
        if not order_position:
            order_position = order.positions.first()

        profile = {'fields': {}}
        if order_position.attendee_name:
            profile['display_name'] = order_position.attendee_name
        if order_position.company:
            profile['fields']['company'] = order_position.company

        for a in order_position.answers.filter(
            question_id__in=self.request.event.settings.venueless_questions
        ).select_related('question'):
            profile['fields'][a.question.identifier] = a.answer

        uid_token = encode_email(order.email) if order.email else order_position.pseudonymization_id
        iat = dt.datetime.now(dt.UTC)
        exp = iat + dt.timedelta(days=30)

        is_user_staff = bool(
            self.request.user.is_authenticated
            and (
                getattr(self.request.user, 'is_staff', False)
                or getattr(self.request.user, 'is_superuser', False)
                or self.request.user.has_perm('base.change_event_settings', self.request.event)
            )
        )
        is_user_superuser = bool(
            self.request.user.is_authenticated and getattr(self.request.user, 'is_superuser', False)
        )

        payload = {
            'iss': self.request.event.settings.venueless_issuer,
            'aud': self.request.event.settings.venueless_audience,
            'exp': exp,
            'iat': iat,
            'uid': uid_token,
            'profile': profile,
            'is_staff': is_user_staff,
            'is_superuser': is_user_superuser,
            'traits': list(
                {
                    # Grant base attendee role so the video app allows EVENT_VIEW by default
                    # Without this, users with valid tickets received auth.denied because
                    # none of the event trait_grants matched the token traits.
                    'attendee',
                    'eventyay-video-event-{}'.format(request.event.slug),
                    'eventyay-video-subevent-{}'.format(order_position.subevent_id),
                    'eventyay-video-product-{}'.format(order_position.product_id),
                    'eventyay-video-variation-{}'.format(order_position.variation_id),
                    'eventyay-video-category-{}'.format(order_position.product.category_id),
                }
                | {'eventyay-video-product-{}'.format(p.product_id) for p in order_position.addons.all()}
                | {
                    'eventyay-video-variation-{}'.format(p.variation_id)
                    for p in order_position.addons.all()
                    if p.variation_id
                }
                | {
                    'eventyay-video-category-{}'.format(p.product.category_id)
                    for p in order_position.addons.all()
                    if p.product.category_id
                }
            ),
        }

        token = jwt.encode(payload, self.request.event.settings.venueless_secret, algorithm='HS256')
        baseurl = self.request.event.settings.venueless_url

        # Ensure the URL includes the event identifier so VideoSPAView has event context
        # Format: http://localhost:8000/organizer-slug/event-slug/video/#token=...
        # Use Django's reverse() to properly construct the video URL path
        video_path = reverse('video.spa', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })

        # Parse the base URL to get scheme and netloc (domain)
        parsed = urlparse(baseurl)

        # Reconstruct the full URL with the proper path from reverse()
        baseurl = urlunparse((parsed.scheme, parsed.netloc, video_path, '', '', ''))

        return '{}/#token={}'.format(baseurl, token).replace('//#', '/#')
