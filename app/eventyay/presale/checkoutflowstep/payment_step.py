import inspect
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from eventyay.base.services.cart import get_fees
from eventyay.presale.views import CartMixin, get_cart, get_cart_total

from .template_flow_step import TemplateFlowStep


class PaymentStep(CartMixin, TemplateFlowStep):
    priority = 200
    identifier = 'payment'
    template_name = 'eventyaypresale/event/checkout_payment.html'
    label = pgettext_lazy('checkoutflow', 'Payment')
    icon = 'credit-card'

    @cached_property
    def _total_order_value(self):
        cart = get_cart(self.request)
        total = get_cart_total(self.request)
        total += sum(
            [
                f.value
                for f in get_fees(
                    self.request.event,
                    self.request,
                    total,
                    self.invoice_address,
                    None,
                    cart,
                )
            ]
        )
        return Decimal(total)

    @cached_property
    def provider_forms(self):
        providers = []
        payment_providers = self.request.event.get_payment_providers().values()
        sorted_providers = sorted(payment_providers, key=lambda p: str(p.public_name))

        for provider in sorted_providers:
            if not provider.is_enabled or not self._is_allowed(provider, self.request):
                continue

            # Calculate fee and form
            fee = provider.calculate_fee(self._total_order_value)

            if 'total' in inspect.signature(provider.payment_form_render).parameters:
                form = provider.payment_form_render(self.request, self._total_order_value + fee)
            else:
                form = provider.payment_form_render(self.request)

            # Append provider info to list
            providers.append(
                {
                    'provider': provider,
                    'fee': fee,
                    'total': self._total_order_value + fee,
                    'form': form,
                }
            )

        return providers

    def post(self, request):
        self.request = request
        payment_identifier = request.POST.get('payment', '')
        for provider_form in self.provider_forms:
            provider = provider_form['provider']

            if provider.identifier == payment_identifier:
                self.cart_session['payment'] = provider.identifier
                response = provider.checkout_prepare(request, self.get_cart())

                if isinstance(response, str):
                    return redirect(response)
                elif response is True:
                    return redirect(self.get_next_url(request))
                else:
                    return self.render()

        messages.error(self.request, _('Please select a payment method.'))
        return self.render()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['providers'] = self.provider_forms
        ctx['show_fees'] = any(p['fee'] for p in self.provider_forms)
        ctx['selected'] = self.request.POST.get('payment', self.cart_session.get('payment', ''))
        if len(self.provider_forms) == 1:
            ctx['selected'] = self.provider_forms[0]['provider'].identifier
        ctx['cart'] = self.get_cart()
        return ctx

    @cached_property
    def payment_provider(self):
        return self.request.event.get_payment_providers().get(self.cart_session['payment'])

    def _is_allowed(self, prov, request):
        return prov.is_allowed(request, total=self._total_order_value)

    def is_completed(self, request, warn=False):
        self.request = request
        if 'payment' not in self.cart_session or not self.payment_provider:
            if warn:
                messages.error(request, _('The payment information you entered was incomplete.'))
            return False
        if (
            not self.payment_provider.payment_is_valid_session(request)
            or not self.payment_provider.is_enabled
            or not self._is_allowed(self.payment_provider, request)
        ):
            if warn:
                messages.error(request, _('The payment information you entered was incomplete.'))
            return False
        return True

    def is_applicable(self, request):
        self.request = request

        for cartpos in get_cart(self.request):
            if cartpos.item.require_approval:
                if 'payment' in self.cart_session:
                    del self.cart_session['payment']
                return False

        for p in self.request.event.get_payment_providers().values():
            if p.is_implicit(request) if callable(p.is_implicit) else p.is_implicit:
                if self._is_allowed(p, request):
                    self.cart_session['payment'] = p.identifier
                    return False
                elif self.cart_session.get('payment') == p.identifier:
                    # is_allowed might have changed, e.g. after add-on selection
                    del self.cart_session['payment']

        return True
