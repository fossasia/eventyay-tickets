from django.http import HttpResponseNotAllowed
from django.utils.functional import cached_property
from django.utils.translation import pgettext_lazy
from django_scopes import scopes_disabled

from pretix.base.models import InvoiceAddress
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.views.cart import cart_session


class BaseCheckoutFlowStep:
    requires_valid_cart = True
    icon = 'pencil'

    def __init__(self, event):
        self.event = event
        self.request = None

    @property
    def identifier(self):
        raise NotImplementedError()

    @property
    def label(self):
        return pgettext_lazy('checkoutflow', 'Step')

    @property
    def priority(self):
        return 100

    def is_applicable(self, request):
        return True

    def is_completed(self, request, warn=False):
        raise NotImplementedError()

    def get_next_applicable(self, request):
        if hasattr(self, '_next') and self._next:
            if not self._next.is_applicable(request):
                return self._next.get_next_applicable(request)
            return self._next

    def get_prev_applicable(self, request):
        if hasattr(self, '_previous') and self._previous:
            if not self._previous.is_applicable(request):
                return self._previous.get_prev_applicable(request)
            return self._previous

    def get(self, request):
        return HttpResponseNotAllowed([])

    def post(self, request):
        return HttpResponseNotAllowed([])

    def get_step_url(self, request):
        kwargs = {'step': self.identifier}
        if request.resolver_match and 'cart_namespace' in request.resolver_match.kwargs:
            kwargs['cart_namespace'] = request.resolver_match.kwargs['cart_namespace']
        return eventreverse(self.event, 'presale:event.checkout', kwargs=kwargs)

    def get_prev_url(self, request):
        prev = self.get_prev_applicable(request)
        if not prev:
            kwargs = {}
            if (
                request.resolver_match
                and 'cart_namespace' in request.resolver_match.kwargs
            ):
                kwargs['cart_namespace'] = request.resolver_match.kwargs[
                    'cart_namespace'
                ]
            return eventreverse(
                self.request.event, 'presale:event.index', kwargs=kwargs
            )
        else:
            return prev.get_step_url(request)

    def get_next_url(self, request):
        n = self.get_next_applicable(request)
        if n:
            return n.get_step_url(request)

    @cached_property
    def cart_session(self):
        return cart_session(self.request)

    @cached_property
    def invoice_address(self):
        if not hasattr(self.request, '_checkout_flow_invoice_address'):
            iapk = self.cart_session.get('invoice_address')
            if not iapk:
                self.request._checkout_flow_invoice_address = InvoiceAddress()
            else:
                try:
                    with scopes_disabled():
                        self.request._checkout_flow_invoice_address = (
                            InvoiceAddress.objects.get(pk=iapk, order__isnull=True)
                        )
                except InvoiceAddress.DoesNotExist:
                    self.request._checkout_flow_invoice_address = InvoiceAddress()
        return self.request._checkout_flow_invoice_address
