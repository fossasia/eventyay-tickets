import json
import logging
from decimal import Decimal
from urllib.parse import quote

from django.contrib import messages
from django.core import signing
from django.core.cache import cache
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic.base import TemplateResponseMixin, ContextMixin
from django_scopes import scopes_disabled
from paypalcheckoutsdk import orders as pp_orders, payments as pp_payments

from pretix.base.models import Event, Order, OrderPayment, OrderRefund, Quota, TaxRule
from pretix.base.payment import PaymentException
from pretix.base.services.cart import add_payment_to_cart, get_fees
from pretix.base.settings import GlobalSettingsObject
from pretix.control.permissions import event_permission_required
from pretix.helpers.http import redirect_to_url
from pretix.multidomain.urlreverse import eventreverse
from pretix.plugins.paypal.models import ReferencedPayPalObject
from pretix.plugins.paypal.payment import (
    PaypalMethod, PaypalMethod as Paypal, PaypalWallet
)
from pretix.presale.views import get_cart_total, get_cart
from pretix.presale.views.cart import cart_session

logger = logging.getLogger('pretix.plugins.paypal')


@xframe_options_exempt
def redirect_view(request, *args, **kwargs):
    signer = signing.Signer(salt='safe-redirect')
    try:
        url = signer.unsign(request.GET.get('url', ''))
    except signing.BadSignature:
        return HttpResponseBadRequest('Invalid parameter')

    r = render(request, 'plugins/paypal/redirect.html', {
        'url': url,
    })
    r._csp_ignore = True
    return r


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(xframe_options_exempt, 'dispatch')
class XHRView(View):

    def post(self, request, *args, **kwargs):
        if 'order' in self.kwargs:
            order = self.request.event.orders.filter(code=self.kwargs['order']).select_related('event').first()
            if order:
                if order.secret.lower() == self.kwargs['secret'].lower():
                    pass
                else:
                    order = None
        else:
            order = None

        prov = PaypalMethod(request.event)

        if order:
            lp = order.payments.last()
            if lp and lp.fee and lp.state not in (
                    OrderPayment.PAYMENT_STATE_CONFIRMED, OrderPayment.PAYMENT_STATE_REFUNDED
            ):
                fee = lp.fee.value - prov.calculate_fee(order.pending_sum - lp.fee.value)
            else:
                fee = prov.calculate_fee(order.pending_sum)

            cart_total = order.pending_sum + fee
        else:
            cart_total = get_cart_total(request)
            cart_payments = cart_session(request).get('payments', [])
            multi_use_cart_payments = [p for p in cart_payments if p.get('multi_use_supported')]
            simulated_payments = multi_use_cart_payments + [{
                'provider': 'paypal',
                'multi_use_supported': False,
                'min_value': None,
                'max_value': None,
                'info_data': {},
            }]

            try:
                for fee in get_fees(request.event, request, cart_total, None, simulated_payments, get_cart(request)):
                    cart_total += fee.value
            except TaxRule.SaleNotAllowed:
                pass

            total_remaining = cart_total
            for p in multi_use_cart_payments:
                if p.get('min_value') and total_remaining < Decimal(p['min_value']):
                    continue

                to_pay = total_remaining
                if p.get('max_value') and to_pay > Decimal(p['max_value']):
                    to_pay = min(to_pay, Decimal(p['max_value']))
                total_remaining -= to_pay

            cart_total = total_remaining

        paypal_order = prov.create_paypal_order(request, None, cart_total)
        r = JsonResponse(paypal_order.dict() if paypal_order else {})
        r._csp_ignore = True
        return r


class PartnersMerchantIntegrationsGetRequest:
    """
    Retrieves the Merchant Account Status of a Partner Merchant Integration.
    """

    def __init__(self, partner_merchant_id, seller_merchant_id):
        self.verb = "GET"
        self.path = "/v1/customer/partners/{partner_merchant_id}/merchant-integrations/{seller_merchant_id}".format(
            partner_merchant_id=quote(str(partner_merchant_id)),
            seller_merchant_id=quote(str(seller_merchant_id))
        )
        self.headers = {"Content-Type": "application/json"}
        self.body = None

    def prefer(self, prefer):
        self.headers["Prefer"] = str(prefer)


@scopes_disabled()
@event_permission_required('can_change_event_settings')
def isu_return(request, *args, **kwargs):
    getparams = ['merchantId', 'merchantIdInPayPal', 'permissionsGranted', 'accountStatus',
                 'consentStatus', 'productIntentId', 'isEmailConfirmed']
    session_params = ['payment_paypal_isu_event', 'payment_paypal_isu_tracking_id']
    if not any(k in request.GET for k in getparams) or not any(k in request.session for k in session_params):
        messages.error(request, _('An error occurred returning from PayPal: request parameters missing. Please try '
                                  'again.'))
        missing_getparams = set(getparams) - set(request.GET)
        missing_session_params = {p for p in session_params if p not in request.session}
        logger.exception('PayPal - Missing params in GET {} and/or Session {}'
                         .format(missing_getparams, missing_session_params))
        return redirect('control:index')

    event = get_object_or_404(Event, pk=request.session['payment_paypal_isu_event'])
    try:
        cache.incr('paypal_token_hash_cycle')
    except ValueError:
        cache.set('paypal_token_hash_cycle', 1, None)

    gs = GlobalSettingsObject()
    prov = Paypal(event)
    prov.init_api()

    try:
        req = PartnersMerchantIntegrationsGetRequest(
            gs.settings.get('payment_paypal_connect_partner_merchant_id'),
            request.GET.get('merchantIdInPayPal')
        )
        response = prov.client.execute(req)
    except IOError as e:
        messages.error(request, _('An error occurred during connecting with PayPal, please try again.'))
        logger.exception('PayPal - PartnersMerchantIntegrationsGetRequest: {}'.format(str(e)))
    else:
        params = ['merchant_id', 'tracking_id', 'payments_receivable', 'primary_email_confirmed']
        if not any(k in response.result for k in params):
            if 'message' in response.result:
                messages.error(request, response.result.message)
                logger.exception('PayPal - Error-message in response: {}'.format(response.result.message))
            else:
                messages.error(request, _('An error occurred returning from PayPal: '
                                          'result parameters missing. Please try again.'))
                missing_params = set(params) - set(response.result)
                logger.exception('PayPal - Missing params {} in response.result'.format(missing_params))
        else:
            if response.result.tracking_id != request.session['payment_paypal_isu_tracking_id']:
                messages.error(request, _('An error occurred returning from PayPal: '
                                          'session parameter not matching. Please try again.'))
                logger.exception('PayPal - tracking_id not matching session.payment_paypal_isu_tracking_id')
            elif request.GET.get("isEmailConfirmed") == "false":
                messages.error(
                    request,
                    _('The e-mail address on your PayPal account has not yet been confirmed. You will need to do '
                      'this before you can start accepting payments.')
                )
            else:
                messages.success(
                    request,
                    _('Your PayPal account is now connected to Eventyay. You can change the settings in detail below.')
                )

                event.settings.payment_paypal_isu_merchant_id = response.result.merchant_id

                for integration in response.result.oauth_integrations:
                    if integration.integration_type == 'OAUTH_THIRD_PARTY':
                        for third_party in integration.oauth_third_party:
                            if third_party.partner_client_id == prov.client.environment.client_id:
                                event.settings.payment_paypal_isu_scopes = third_party.scopes

    return redirect_to_url(reverse('control:event.settings.payment.provider', kwargs={
        'organizer': event.organizer.slug,
        'event': event.slug,
        'provider': 'paypal_settings'
    }))


def success(request, *args, **kwargs):
    token = request.GET.get('token')
    payer = request.GET.get('PayerID')
    request.session['payment_paypal_token'] = token
    request.session['payment_paypal_payer'] = payer

    url_kwargs = {}
    if 'cart_namespace' in kwargs:
        url_kwargs['cart_namespace'] = kwargs['cart_namespace']

    if request.session.get('payment_paypal_payment'):
        payment = OrderPayment.objects.get(pk=request.session.get('payment_paypal_payment'))
    else:
        payment = None

    if request.session.get('payment_paypal_oid', None):
        if payment:
            prov = Paypal(request.event)
            try:
                resp = prov.execute_payment(request, payment)
            except PaymentException as e:
                messages.error(request, str(e))
                url_kwargs['step'] = 'payment'
                return redirect(eventreverse(request.event, 'presale:event.checkout', kwargs=url_kwargs))
            if resp:
                return resp
    else:
        messages.error(request, _('Invalid response from PayPal received.'))
        logger.error('Session did not contain payment_paypal_oid')
        url_kwargs['step'] = 'payment'
        return redirect(eventreverse(request.event, 'presale:event.checkout', kwargs=url_kwargs))

    if payment:
        return redirect(eventreverse(request.event, 'presale:event.order', kwargs={
            'order': payment.order.code,
            'secret': payment.order.secret
        }) + ('?paid=yes' if payment.order.status == Order.STATUS_PAID else ''))
    else:
        cs = cart_session(request)
        cs['payments'] = [p for p in cs.get('payments', []) if p.get('multi_use_supported')]
        add_payment_to_cart(request, PaypalWallet(request.event), None, None, None)
        url_kwargs['step'] = 'confirm'
        return redirect(eventreverse(request.event, 'presale:event.checkout', kwargs=url_kwargs))


def abort(request, *args, **kwargs):
    messages.error(request, _('It looks like you canceled the PayPal payment'))

    if request.session.get('payment_paypal_payment'):
        payment = OrderPayment.objects.get(pk=request.session.get('payment_paypal_payment'))
    else:
        payment = None

    if payment:
        return redirect(eventreverse(request.event, 'presale:event.order', kwargs={
            'order': payment.order.code,
            'secret': payment.order.secret
        }) + ('?paid=yes' if payment.order.status == Order.STATUS_PAID else ''))
    else:
        return redirect(eventreverse(request.event, 'presale:event.checkout', kwargs={'step': 'payment'}))


@csrf_exempt
@require_POST
@scopes_disabled()
def webhook(request, *args, **kwargs):
    event_body = request.body.decode('utf-8').strip()
    event_json = json.loads(event_body)

    if 'event_type' not in event_json:
        return HttpResponse("Invalid body, no event_type given", status=400)

    if 'resource_type' not in event_json:
        return HttpResponse("Invalid body, no resource_type given", status=400)

    if event_json['resource_type'] not in ["checkout-order", "refund", "capture"]:
        return HttpResponse("Not interested in this resource type", status=200)

    def get_link(links, rel):
        for link in links:
            if link['rel'] == rel:
                return link

        return None

    if event_json['resource_type'] == 'refund':
        payloadid = get_link(event_json['resource']['links'], 'up')['href'].split('/')[-1]
    else:
        payloadid = event_json['resource']['id']

    refs = [payloadid]
    if event_json['resource'].get('supplementary_data', {}).get('related_ids', {}).get('order_id'):
        refs.append(event_json['resource'].get('supplementary_data').get('related_ids').get('order_id'))

    rso = ReferencedPayPalObject.objects.select_related('order', 'order__event').filter(
        reference__in=refs
    ).first()
    if rso:
        event = rso.order.event
    else:
        rso = None
        if hasattr(request, 'event'):
            event = request.event
        else:
            return HttpResponse("Unable to detect event", status=200)

    prov = PaypalMethod(event)
    prov.init_api()

    try:
        if rso and 'id' in rso.payment.info_data:
            payloadid = rso.payment.info_data['id']
        sale = prov.client.execute(pp_orders.OrdersGetRequest(payloadid)).result
    except IOError:
        logger.exception('PayPal error on webhook. Event data: %s' % str(event_json))
        return HttpResponse('Sale not found', status=500)

    if rso and rso.payment:
        payment = rso.payment
    else:
        payments = OrderPayment.objects.filter(order__event=event, provider='paypal',
                                               info__icontains=sale['id'])
        payment = None
        for p in payments:
            if "purchase_units" not in p.info_data:
                try:
                    req = pp_orders.OrdersGetRequest(p.info_data['cart'])
                    response = prov.client.execute(req)
                    p.info = json.dumps(response.result.dict())
                    p.save(update_fields=['info'])
                    p.refresh_from_db()
                except IOError:
                    logger.exception('PayPal error on webhook. Event data: %s' % str(event_json))
                    return HttpResponse('Could not retrieve Order Data', status=500)

            for res in p.info_data['purchase_units'][0]['payments']['captures']:
                if res['status'] in ['COMPLETED', 'PARTIALLY_REFUNDED'] and res['id'] == sale['id']:
                    payment = p
                    break

    if not payment:
        return HttpResponse('Payment not found', status=200)

    payment.order.log_action('pretix.plugins.paypal.event', data={
        **event_json,
        '_order_state': sale.dict(),
    })

    if payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED and sale['status'] in (
            'PARTIALLY_REFUNDED', 'REFUNDED', 'COMPLETED'):
        if event_json['resource_type'] == 'refund':
            try:
                req = pp_payments.RefundsGetRequest(event_json['resource']['id'])
                refund = prov.client.execute(req).result
            except IOError:
                logger.exception('PayPal error on webhook. Event data: %s' % str(event_json))
                return HttpResponse('Refund not found', status=500)

            known_refunds = {r.info_data.get('id'): r for r in payment.refunds.all()}
            if refund['id'] not in known_refunds:
                payment.create_external_refund(
                    amount=abs(Decimal(refund['amount']['value'])),
                    info=json.dumps(refund.dict() if not isinstance(refund, dict) else refund)
                )
            elif known_refunds.get(refund['id']).state in (
                    OrderRefund.REFUND_STATE_CREATED, OrderRefund.REFUND_STATE_TRANSIT) and refund[
                'status'] == 'COMPLETED':
                known_refunds.get(refund['id']).done()

            if 'seller_payable_breakdown' in refund and 'total_refunded_amount' in refund['seller_payable_breakdown']:
                known_sum = payment.refunds.filter(
                    state__in=(OrderRefund.REFUND_STATE_DONE, OrderRefund.REFUND_STATE_TRANSIT,
                               OrderRefund.REFUND_STATE_CREATED, OrderRefund.REFUND_SOURCE_EXTERNAL)
                ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
                total_refunded_amount = Decimal(refund['seller_payable_breakdown']['total_refunded_amount']['value'])
                if known_sum < total_refunded_amount:
                    payment.create_external_refund(
                        amount=total_refunded_amount - known_sum
                    )
        elif sale['status'] == 'REFUNDED':
            known_sum = payment.refunds.filter(
                state__in=(OrderRefund.REFUND_STATE_DONE, OrderRefund.REFUND_STATE_TRANSIT,
                           OrderRefund.REFUND_STATE_CREATED, OrderRefund.REFUND_SOURCE_EXTERNAL)
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

            if known_sum < payment.amount:
                payment.create_external_refund(
                    amount=payment.amount - known_sum
                )
    elif payment.state in (OrderPayment.PAYMENT_STATE_PENDING, OrderPayment.PAYMENT_STATE_CREATED,
                           OrderPayment.PAYMENT_STATE_CANCELED, OrderPayment.PAYMENT_STATE_FAILED):
        if sale['status'] == 'COMPLETED':
            any_captures = False
            all_captures_completed = True
            for purchaseunit in sale['purchase_units']:
                for capture in purchaseunit['payments']['captures']:
                    try:
                        ReferencedPayPalObject.objects.get_or_create(order=payment.order, payment=payment,
                                                                     reference=capture['id'])
                    except ReferencedPayPalObject.MultipleObjectsReturned:
                        pass

                    if capture['status'] not in ('COMPLETED', 'REFUNDED', 'PARTIALLY_REFUNDED'):
                        all_captures_completed = False
                    else:
                        any_captures = True
            if any_captures and all_captures_completed:
                try:
                    payment.info = json.dumps(sale.dict())
                    payment.save(update_fields=['info'])
                    payment.confirm()
                except Quota.QuotaExceededException:
                    pass
        elif sale['status'] == 'APPROVED':
            request.session['payment_paypal_oid'] = payment.info_data['id']
            try:
                payment.payment_provider.execute_payment(request, payment)
            except PaymentException as e:
                logger.exception('PayPal - Could not capture/execute_payment from Webhook: {}'.format(str(e)))

    return HttpResponse(status=200)


@event_permission_required('can_change_event_settings')
@require_POST
def isu_disconnect(request, **kwargs):
    del request.event.settings.payment_paypal_connect_refresh_token
    del request.event.settings.payment_paypal_connect_user_id
    del request.event.settings.payment_paypal_isu_merchant_id
    del request.event.settings.payment_paypal_isu_scopes
    request.event.settings.payment_paypal__enabled = False
    messages.success(request, _('Your PayPal account has been disconnected.'))

    return redirect(reverse('control:event.settings.payment.provider', kwargs={
        'organizer': request.event.organizer.slug,
        'event': request.event.slug,
        'provider': 'paypal_settings'
    }))


class PaypalOrderView(View):
    """
    A Django view to handle PayPal order-related actions, such as redirecting
    to the order page after payment processing.
    """

    def dispatch(self, request, *args, **kwargs):
        """
        Override the dispatch method to retrieve the order based on the provided
        order code and secret hash. If the order is not found, raise a 404 error.

        :param request: The HTTP request object.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments, including 'order' and 'hash'.
        :return: The result of the superclass dispatch method.
        """
        try:
            self.order = request.event.orders.get_with_secret_check(
                code=kwargs['order'], received_secret=kwargs['hash'].lower(), tag='plugins:paypal:pay'
            )
        except Order.DoesNotExist:
            raise Http404('Unknown order')
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def payment(self):
        """
        Cached property to retrieve the payment object associated with the order.
        If the payment is not found, raise a 404 error.

        :return: The payment object.
        """
        return get_object_or_404(
            self.order.payments,
            pk=self.kwargs['payment'],
            provider__istartswith='paypal',
        )

    def _redirect_to_order(self):
        """
        Redirect to the order page. If the order is paid, append a query parameter
        to indicate the payment status.

        :return: An HTTP redirect response to the order page.
        """
        return redirect(eventreverse(self.request.event, 'presale:event.order', kwargs={
            'order': self.order.code,
            'secret': self.order.secret
        }) + ('?paid=yes' if self.order.status == Order.STATUS_PAID else ''))


class TemplateView(TemplateResponseMixin, ContextMixin, View):
    """
    A Django view to render a template with a given context.

    This view combines the functionality of TemplateResponseMixin and ContextMixin
    to provide a simple way to render a template with context data.
    """

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests and return a rendered template response.

        This method retrieves the context data using the get_context_data method
        and renders the template with this context.

        :param request: The HTTP request object.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: A rendered template response.
        """
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


@method_decorator(xframe_options_exempt, 'dispatch')
class PayView(PaypalOrderView, TemplateView):
    """
    A Django view to handle PayPal payment interactions.

    This view combines the functionality of PaypalOrderView and TemplateView
    to manage both GET and POST requests for PayPal payments.
    """
    template_name = 'plugins/paypal/paypal_pay.html'

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests to render the PayPal payment page.

        If the payment state is not 'created', it redirects to the order page.
        Otherwise, it renders the payment template.

        :param request: The HTTP request object.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: A rendered template response or a redirect response.
        """
        if self.payment.state != OrderPayment.PAYMENT_STATE_CREATED:
            return self._redirect_to_order()
        else:
            return render(request, self.template_name, self.get_context_data())

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests to execute the PayPal payment.

        This method attempts to execute the payment using the payment provider.
        If an exception occurs, it displays an error message and redirects to the order page.

        :param request: The HTTP request object.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: A redirect response to the order page.
        """
        try:
            self.payment.payment_provider.execute_payment(request, self.payment)
        except PaymentException as e:
            messages.error(request, str(e))
        return self._redirect_to_order()

    def get_context_data(self, **kwargs):
        """
        Get the context data for rendering the template.

        This method adds the order, PayPal order ID, and payment method to the context.

        :param kwargs: Additional keyword arguments.
        :return: A dictionary containing the context data.
        """
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        ctx['oid'] = self.payment.info_data['id']
        ctx['method'] = self.payment.payment_provider.method
        return ctx
