from collections import defaultdict

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils.translation import (
    get_language, gettext_lazy as _, pgettext_lazy,
)

from pretix.base.models.tax import TaxedPrice
from pretix.base.services.cart import (
    CartError, error_messages, set_cart_addons,
)
from pretix.base.signals import validate_cart_addons
from pretix.base.views.tasks import AsyncAction
from pretix.presale.views import CartMixin, get_cart
from pretix.presale.views.cart import get_or_create_cart_id
from pretix.presale.views.event import get_grouped_items

from .template_flow_step import TemplateFlowStep


class AddOnsStep(CartMixin, AsyncAction, TemplateFlowStep):
    priority = 40
    identifier = "addons"
    template_name = "pretixpresale/event/checkout_addons.html"
    task = set_cart_addons
    known_errortypes = ['CartError']
    requires_valid_cart = False
    label = pgettext_lazy('checkoutflow', 'Add-on products')
    icon = 'puzzle-piece'

    def is_applicable(self, request):
        if not hasattr(request, '_checkoutflow_addons_applicable'):
            request._checkoutflow_addons_applicable = get_cart(request).filter(item__addons__isnull=False).exists()
        return request._checkoutflow_addons_applicable

    def is_completed(self, request, warn=False):
        if getattr(self, '_completed', None) is not None:
            return self._completed
        cart_positions = (
            get_cart(request)
            .filter(addon_to__isnull=True)
            .prefetch_related(
                'item__addons',
                'item__addons__addon_category',
                'addons',
                'addons__item'
            )
        )

        for cartpos in cart_positions:
            a = cartpos.addons.all()
            for addon in cartpos.item.addons.all():
                count = sum(1 for item in a if item.item.category_id == addon.addon_category_id and not item.is_bundled)
                if not addon.min_count <= count <= addon.max_count:
                    self._completed = False
                    return False
        self._completed = True
        return True

    @cached_property
    def forms(self):
        """
        A list of forms with one form for each cart position that can have add-ons.
        All forms have a custom prefix, so that they can all be submitted at once.
        """
        formset = []
        quota_cache = {}
        item_cache = {}
        cart_positions = (
            get_cart(self.request)
            .filter(addon_to__isnull=True)
            .prefetch_related(
                'item__addons',
                'item__addons__addon_category',
                'addons',
                'addons__variation'
            )
            .order_by('pk')
        )
        for cartpos in cart_positions:
            formsetentry = {
                'cartpos': cartpos,
                'item': cartpos.item,
                'variation': cartpos.variation,
                'categories': []
            }
            formset.append(formsetentry)

            current_addon_products = defaultdict(list)
            for a in cartpos.addons.all():
                if not a.is_bundled:
                    current_addon_products[a.item_id, a.variation_id].append(a)

            for iao in cartpos.item.addons.all():
                ckey = '{}-{}'.format(cartpos.subevent.pk if cartpos.subevent else 0, iao.addon_category.pk)

                if ckey not in item_cache:
                    # Get all items to possibly show
                    items, _btn = get_grouped_items(
                        self.request.event,
                        subevent=cartpos.subevent,
                        voucher=None,
                        channel=self.request.sales_channel.identifier,
                        base_qs=iao.addon_category.items,
                        allow_addons=True,
                        quota_cache=quota_cache
                    )
                    item_cache[ckey] = items
                else:
                    items = item_cache[ckey]

                for i in items:
                    i.allow_waitinglist = False

                    if i.has_variations:
                        for variation in i.available_variations:
                            variation_id = (i.pk, variation.pk)
                            variation.initial = len(current_addon_products[variation_id])

                            if variation.initial and i.free_price:
                                first_addon = current_addon_products[variation_id][0]
                                variation.initial_price = TaxedPrice(
                                    net=first_addon.price - first_addon.tax_value,
                                    gross=first_addon.price,
                                    tax=first_addon.tax_value,
                                    name=first_addon.item.tax_rule.name if first_addon.item.tax_rule else "",
                                    rate=first_addon.tax_rate,
                                )
                            else:
                                variation.initial_price = variation.display_price

                        i.expand = any(v.initial for v in i.available_variations)
                    else:
                        i.initial = len(current_addon_products[i.pk, None])
                        if i.initial and i.free_price:
                            a = current_addon_products[i.pk, None][0]
                            i.initial_price = TaxedPrice(
                                net=a.price - a.tax_value,
                                gross=a.price,
                                tax=a.tax_value,
                                name=a.item.tax_rule.name if a.item.tax_rule else "",
                                rate=a.tax_rate,
                            )
                        else:
                            i.initial_price = i.display_price

                if items:
                    formsetentry['categories'].append({
                        'category': iao.addon_category,
                        'price_included': iao.price_included,
                        'multi_allowed': iao.multi_allowed,
                        'min_count': iao.min_count,
                        'max_count': iao.max_count,
                        'iao': iao,
                        'items': items
                    })
        return formset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['forms'] = self.forms
        ctx['cart'] = self.get_cart()
        return ctx

    def get_success_message(self, value):
        return None

    def get_success_url(self, value):
        return self.get_next_url(self.request)

    def get_error_url(self):
        return self.get_step_url(self.request)

    def get(self, request, **kwargs):
        self.request = request
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return self.get_result(request)
        return TemplateFlowStep.get(self, request)

    def _clean_category(self, form, category):
        selected = {}
        for i in category['items']:
            item_key_base = f'cp_{form["cartpos"].pk}'
            if i.has_variations:
                for v in i.available_variations:
                    variation_key = f'{item_key_base}_variation_{i.pk}_{v.pk}'
                    val = int(self.request.POST.get(variation_key) or '0')
                    price = self.request.POST.get(f'{variation_key}_price') or '0'
                    if val:
                        selected[i, v] = val, price
            else:
                item_key = f'{item_key_base}_item_{i.pk}'
                val = int(self.request.POST.get(item_key) or '0')
                price = self.request.POST.get(f'{item_key}_price') or '0'
                if val:
                    selected[i, None] = val, price

        total_selected_quantity = sum(a[0] for a in selected.values())
        exceeds_single_allowed = any(
            sum(v[0] for k, v in selected.items() if k[0] == i) > 1 for i in category['items']) and not category[
            'multi_allowed']

        if total_selected_quantity > category['max_count']:
            raise ValidationError(
                _(error_messages['addon_max_count']),
                'addon_max_count',
                {
                    'base': str(form['item'].name),
                    'max': category['max_count'],
                    'cat': str(category['category'].name),
                }
            )
        elif total_selected_quantity < category['min_count']:
            raise ValidationError(
                _(error_messages['addon_min_count']),
                'addon_min_count',
                {
                    'base': str(form['item'].name),
                    'min': category['min_count'],
                    'cat': str(category['category'].name),
                }
            )
        elif exceeds_single_allowed:
            raise ValidationError(
                _(error_messages['addon_no_multi']),
                'addon_no_multi',
                {
                    'base': str(form['item'].name),
                    'cat': str(category['category'].name),
                }
            )
        try:
            validate_cart_addons.send(
                sender=self.event,
                addons={k: v[0] for k, v in selected.items()},
                base_position=form["cartpos"],
                iao=category['iao']
            )
        except CartError as e:
            raise ValidationError(str(e))

        return selected

    def post(self, request, *args, **kwargs):
        self.request = request
        data = []
        for f in self.forms:
            for c in f['categories']:
                try:
                    selected = self._clean_category(f, c)
                except ValidationError as e:
                    messages.error(request, e.message % e.params if e.params else e.message)
                    return self.get(request, *args, **kwargs)

                for (i, v), (c, price) in selected.items():
                    data.append({
                        'addon_to': f['cartpos'].pk,
                        'item': i.pk,
                        'variation': v.pk if v else None,
                        'count': c,
                        'price': price,
                    })

        return self.do(self.request.event.id, data, get_or_create_cart_id(self.request),
                       invoice_address=self.invoice_address.pk, locale=get_language(),
                       sales_channel=request.sales_channel.identifier)
