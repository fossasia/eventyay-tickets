import json
from collections import OrderedDict

from django import forms
from django.conf import settings
from django.dispatch import receiver
from django.http import HttpRequest, HttpResponse
from django.template.loader import get_template
from django.urls import resolve
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from pretix.base.forms import SecretKeySettingsField
from pretix.base.middleware import _parse_csp, _merge_csp, _render_csp
from pretix.base.settings import settings_hierarkey
from pretix.base.signals import (
    logentry_display, register_global_settings, register_payment_providers
)
from pretix.plugins.paypal.payment import PaypalMethod
from pretix.presale.signals import html_head, process_response


@receiver(register_payment_providers, dispatch_uid="payment_paypal")
def register_payment_provider(sender, **kwargs):
    from .payment import PaypalSettingsHolder, PaypalAPM, PaypalWallet
    return [PaypalSettingsHolder, PaypalAPM, PaypalWallet]


@receiver(signal=logentry_display, dispatch_uid="paypal_logentry_display")
def pretixcontrol_logentry_display(sender, logentry, **kwargs):
    if logentry.action_type != 'pretix.plugins.paypal.event':
        return

    data = json.loads(logentry.data)
    event_type = data.get('event_type')
    text = None
    plains = {
        'PAYMENT.SALE.COMPLETED': _('Payment completed.'),
        'PAYMENT.SALE.DENIED': _('Payment denied.'),
        'PAYMENT.SALE.REFUNDED': _('Payment refunded.'),
        'PAYMENT.SALE.REVERSED': _('Payment reversed.'),
        'PAYMENT.SALE.PENDING': _('Payment pending.'),
        'CHECKOUT.ORDER.APPROVED': pgettext_lazy('paypal', 'Order approved.'),
        'CHECKOUT.ORDER.COMPLETED': pgettext_lazy('paypal', 'Order completed.'),
        'PAYMENT.CAPTURE.COMPLETED': pgettext_lazy('paypal', 'Capture completed.'),
        'PAYMENT.CAPTURE.PENDING': pgettext_lazy('paypal', 'Capture pending.'),
    }

    if event_type in plains:
        text = plains[event_type]
    else:
        text = event_type

    if text:
        return _('PayPal reported an event: {}').format(text)


@receiver(register_global_settings, dispatch_uid='paypal_global_settings')
def register_global_settings(sender, **kwargs):
    return OrderedDict([
        ('payment_paypal_connect_client_id', forms.CharField(
            label=_('PayPal ISU/Connect: Client ID'),
            required=False,
        )),
        ('payment_paypal_connect_secret_key', SecretKeySettingsField(
            label=_('PayPal ISU/Connect: Secret key'),
            required=False,
        )),
        ('payment_paypal_connect_partner_merchant_id', forms.CharField(
            label=_('PayPal ISU/Connect: Partner Merchant ID'),
            help_text=_('ID of the merchant account which holds branding information for ISU.'),
            required=False,
        )),
        ('payment_paypal_connect_endpoint', forms.ChoiceField(
            label=_('PayPal ISU/Connect Endpoint'),
            initial='live',
            choices=(
                ('live', 'Live'),
                ('sandbox', 'Sandbox'),
            ),
        )),
    ])


@receiver(html_head, dispatch_uid="payment_paypal_html_head")
def html_head_presale(sender, request=None, **kwargs):
    provider = PaypalMethod(sender)
    url = resolve(request.path_info)

    if provider.settings.get('_enabled', as_type=bool) and (
            url.url_name == "event.order.pay.change" or
            url.url_name == "event.order.pay" or
            (url.url_name == "event.checkout" and url.kwargs['step'] == "payment") or
            (url.namespace == "plugins:paypal" and url.url_name == "pay")
    ):
        provider.init_api()
        template = get_template('plugins/paypal/presale_head.html')

        ctx = {
            'client_id': provider.client.environment.client_id,
            'merchant_id': provider.client.environment.merchant_id or '',
            'csp_nonce': _nonce(request),
            'debug': settings.DEBUG,
            'settings': provider.settings,
            'disable_funding': 'sepa' if provider.settings.get('disable_method_sepa', as_type=bool) else '',
            'enable_funding': 'paylater' if provider.settings.get('enable_method_paylater', as_type=bool) else ''
        }

        return template.render(ctx)
    else:
        return ""


@receiver(signal=process_response, dispatch_uid="payment_paypal_middleware_resp")
def signal_process_response(sender, request: HttpRequest, response: HttpResponse, **kwargs):
    provider = PaypalMethod(sender)
    url = resolve(request.path_info)

    if provider.settings.get('_enabled', as_type=bool) and (
            url.url_name == "event.order.pay.change" or
            url.url_name == "event.order.pay" or
            (url.url_name == "event.checkout" and url.kwargs['step'] == "payment") or
            (url.namespace == "plugins:paypal" and url.url_name == "pay")
    ):
        if 'Content-Security-Policy' in response:
            h = _parse_csp(response['Content-Security-Policy'])
        else:
            h = {}

        csps = {
            'script-src': ['https://www.paypal.com', "'nonce-{}'".format(_nonce(request))],
            'frame-src': ['https:', "'nonce-{}'".format(_nonce(request))],
            'connect-src': ['https://www.paypal.com', 'https://www.sandbox.paypal.com'],
            'img-src': ['https://t.paypal.com'],
            'style-src': ["'unsafe-inline'"]
        }

        _merge_csp(h, csps)

        if h:
            response['Content-Security-Policy'] = _render_csp(h)

    return response


settings_hierarkey.add_default('payment_paypal_method_wallet', True, bool)


def _nonce(request):
    if not hasattr(request, "_paypal_nonce"):
        request._paypal_nonce = get_random_string(32)
    return request._paypal_nonce
