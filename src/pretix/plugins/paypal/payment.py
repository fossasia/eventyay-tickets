import json
import logging
import urllib.parse
from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.http import HttpRequest
from django.template.loader import get_template
from django.templatetags.static import static
from django.urls import reverse, resolve
from django.utils.crypto import get_random_string
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext as __, gettext_lazy as _
from django_countries import countries
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString
from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersGetRequest, OrdersPatchRequest, OrdersCaptureRequest
from paypalcheckoutsdk.payments import RefundsGetRequest, CapturesRefundRequest
from paypalhttp import HttpError

from pretix.base.decimal import round_decimal
from pretix.base.forms.questions import guess_country
from pretix.base.models import Event, Order, OrderPayment, OrderRefund, Quota
from pretix.base.payment import BasePaymentProvider, PaymentException
from pretix.base.services.mail import SendMailException
from pretix.base.settings import SettingsSandbox
from pretix.helpers import OF_SELF
from pretix.helpers.urls import build_absolute_uri as build_global_uri
from pretix.multidomain.urlreverse import build_absolute_uri, eventreverse
from pretix.plugins.paypal.models import ReferencedPayPalObject
from pretix.plugins.paypal.paypal_environment import SandboxEnvironment, LiveEnvironment
from pretix.plugins.paypal.paypal_http_client import PayPalHttpClient

logger = logging.getLogger('pretix.plugins.paypal')

SUPPORTED_CURRENCIES = ['AUD', 'BRL', 'CAD', 'CZK', 'DKK', 'EUR', 'HKD', 'HUF', 'INR', 'ILS', 'JPY', 'MYR', 'MXN',
                        'TWD', 'NZD', 'NOK', 'PHP', 'PLN', 'GBP', 'RUB', 'SGD', 'SEK', 'CHF', 'THB', 'USD']

LOCAL_ONLY_CURRENCIES = ['INR']


class PaypalSettingsHolder(BasePaymentProvider):
    identifier = 'paypal_settings'
    verbose_name = _('PayPal')
    is_enabled = False
    is_meta = True
    payment_form_fields = OrderedDict([])

    def __init__(self, event: Event):
        super().__init__(event)
        self.settings = SettingsSandbox('payment', 'paypal', event)

    @property
    def settings_form_fields(self):
        if self.settings.connect_client_id and self.settings.connect_secret_key and not self.settings.secret:
            if self.settings.isu_merchant_id:
                fields = [
                    ('isu_merchant_id',
                     forms.CharField(
                         label=_('PayPal Merchant ID'),
                         disabled=True
                     )),
                ]
            else:
                return {}
        else:
            fields = [
                ('client_id',
                 forms.CharField(
                     label=_('Client ID'),
                     max_length=80,
                     min_length=80,
                     help_text=_('<a target="_blank" rel="noopener" href="{docs_url}">{text}</a>').format(
                         text=_('Click here for a tutorial on how to obtain the required keys'),
                         docs_url='https://developer.paypal.com/api/rest/'
                     )
                 )),
                ('secret',
                 forms.CharField(
                     label=_('Secret'),
                     max_length=80,
                     min_length=80,
                 )),
                ('endpoint',
                 forms.ChoiceField(
                     label=_('Endpoint'),
                     initial='live',
                     choices=(
                         ('live', 'Live'),
                         ('sandbox', 'Sandbox'),
                     ),
                 )),
            ]

        methods = [
            ('method_wallet',
             forms.BooleanField(
                 label=_('PayPal'),
                 required=False,
                 help_text=_(
                     'Even if a customer chooses an Alternative Payment Method, they will always have the option to '
                     'revert back to paying with their PayPal account. For this reason, this payment method is always '
                     'active.'
                 ),
                 disabled=True,
             )),
            ('method_apm',
             forms.BooleanField(
                 label=_('Alternative Payment Methods'),
                 help_text=_(
                     'In addition to payments through a PayPal account, you can also offer your customers the option '
                     'to pay with credit cards and other, local payment methods such as SOFORT, giropay, iDEAL, and '
                     'many more - even when they do not have a PayPal account. Eligible payment methods will be '
                     'determined based on the shoppers location. For German merchants, this is the direct successor '
                     'of PayPal Plus.'
                 ),
                 required=False,
                 widget=forms.CheckboxInput(
                     attrs={
                         'data-checkbox-dependency': '#id_payment_paypal_method_wallet',
                     }
                 )
             )),
            ('disable_method_sepa',
             forms.BooleanField(
                 label=_('Disable SEPA Direct Debit'),
                 help_text=_(
                     'While most payment methods cannot be recalled by a customer without outlining their exact grief '
                     'with the merchants, SEPA Direct Debit can be recalled with the press of a button. For that '
                     'reason - and depending on the nature of your event - you might want to disabled the option of '
                     'SEPA Direct Debit payments in order to reduce the risk of costly chargebacks.'
                 ),
                 required=False,
                 widget=forms.CheckboxInput(
                     attrs={
                         'data-checkbox-dependency': '#id_payment_paypal_method_apm',
                     }
                 )
             )),
            ('enable_method_paylater',
             forms.BooleanField(
                 label=_('Enable Buy Now Pay Later'),
                 help_text=_(
                     'Offer your customers the possibility to buy now (up to a certain limit) '
                     'and pay in multiple installments '
                     'or within 30 days. You, as the merchant, are getting your money right away.'
                 ),
                 required=False,
                 widget=forms.CheckboxInput(
                     attrs={
                         'data-checkbox-dependency': '#id_payment_paypal_method_apm',
                     }
                 )
             )),

        ]

        extra_fields = [
            ('prefix',
             forms.CharField(
                 label=_('Reference prefix'),
                 help_text=_('Any value entered here will be added in front of the regular booking reference '
                             'containing the order number.'),
                 required=False,
             )),
            ('postfix',
             forms.CharField(
                 label=_('Reference postfix'),
                 help_text=_('Any value entered here will be added behind the regular booking reference '
                             'containing the order number.'),
                 required=False,
             )),
        ]

        if settings.DEBUG:
            allcountries = list(countries)
            allcountries.insert(0, ('', _('-- Automatic --')))

            extra_fields.append(
                ('debug_buyer_country',
                 forms.ChoiceField(
                     choices=allcountries,
                     label=mark_safe('<span class="label label-primary">DEBUG</span> {}'.format(_('Buyer country'))),
                     initial=guess_country(self.event),
                 )),
            )

        d = OrderedDict(
            fields + methods + extra_fields + list(super().settings_form_fields.items())
        )

        d.move_to_end('prefix')
        d.move_to_end('postfix')
        d.move_to_end('_enabled', False)
        return d

    def settings_content_render(self, request):
        settings_content = ""
        if self.settings.connect_client_id and self.settings.connect_secret_key and not self.settings.secret:
            if not self.settings.isu_merchant_id:
                isu_referral_url = self.get_isu_referral_url(request)
                settings_content = (
                    "<p>{}</p>"
                    "<a href='{}' class='btn btn-primary btn-lg {}'>{}</a>"
                ).format(
                    _('To accept payments via PayPal, you will need a PayPal account. '
                      'By clicking the button below, you can either create a '
                      'new PayPal account or connect an existing one to Eventyay.'),
                    isu_referral_url,
                    'disabled' if not isu_referral_url else '',
                    _('Connect with {icon} PayPal').format(icon='<i class="fa fa-paypal"></i>')
                )
            else:
                settings_content = (
                    "<button formaction='{}' class='btn btn-danger'>{}</button>"
                ).format(
                    reverse('plugins:paypal:isu.disconnect', kwargs={
                        'organizer': self.event.organizer.slug,
                        'event': self.event.slug,
                    }),
                    _('Disconnect from PayPal')
                )
        else:
            settings_content = "<div class='alert alert-info'>%s<br /><code>%s</code></div>" % (
                _('Please set up a PayPal Webhook to the following endpoint to automatically '
                  'cancel orders when payments are refunded externally.'),
                build_global_uri('plugins:paypal:webhook')
            )

        if self.event.currency not in SUPPORTED_CURRENCIES:
            settings_content += (
                                    '<br><br><div class="alert alert-warning">%s '
                                    '<a href="https://developer.paypal.com/docs/api/reference/currency-codes/">%s</a>'
                                    '</div>'
                                ) % (
                                    _("PayPal does not process payments in your event's currency."),
                                    _("Please check this PayPal page for a complete list of supported currencies.")
                                )

        if self.event.currency in LOCAL_ONLY_CURRENCIES:
            settings_content += '<br><br><div class="alert alert-warning">%s''</div>' % (
                _("Your event's currency is supported by PayPal only for in-country accounts. "
                  "This means that both the receiving and sending PayPal accounts must be created in the same "
                  "country and use the same currency. Accounts from other countries "
                  "will not be able to send any payments.")
            )

        return settings_content

    def get_isu_referral_url(self, request):
        paypal_method = PaypalMethod(request.event)
        paypal_method.init_api()

        request.session['payment_paypal_isu_event'] = request.event.pk
        request.session['payment_paypal_isu_tracking_id'] = get_random_string(length=127)

        try:
            req = PartnerReferralCreateRequest()

            req.request_body({
                "operations": [
                    {
                        "operation": "API_INTEGRATION",
                        "api_integration_preference": {
                            "rest_api_integration": {
                                "integration_method": "PAYPAL",
                                "integration_type": "THIRD_PARTY",
                                "third_party_details": {
                                    "features": [
                                        "PAYMENT",
                                        "REFUND",
                                        "ACCESS_MERCHANT_INFORMATION"
                                    ],
                                }
                            }
                        }
                    }
                ],
                "products": [
                    "EXPRESS_CHECKOUT"
                ],
                "partner_config_override": {
                    "partner_logo_url": urllib.parse.urljoin(settings.SITE_URL,
                                                             static('pretixbase/img/eventyay-logo.svg')),
                    "return_url": build_global_uri('plugins:paypal:isu.return', kwargs={
                        'organizer': self.event.organizer.slug,
                        'event': self.event.slug,
                    })
                },
                "tracking_id": request.session['payment_paypal_isu_tracking_id'],
                "preferred_language_code": request.user.locale.split('-')[0]
            })
            response = paypal_method.client.execute(req)
        except IOError as e:
            messages.error(request, _('An error occurred during connecting with PayPal, please try again.'))
            logger.exception('PayPal PartnerReferralCreateRequest: {}'.format(str(e)))
        else:
            return self.get_link(response.result.links, 'action_url').href

    def get_link(self, links, rel):
        for link in links:
            if link.rel == rel:
                return link

        return None


class PartnerReferralCreateRequest:
    """
    Creates a Partner Referral.
    """

    def __init__(self):
        self.verb = "POST"
        self.path = "/v2/customer/partner-referrals?"
        self.headers = {}
        self.headers["Content-Type"] = "application/json"
        self.body = None

    def prefer(self, prefer):
        self.headers["Prefer"] = str(prefer)

    def request_body(self, order):
        self.body = order
        return self


class PaypalMethod(BasePaymentProvider):
    identifier = ''
    method = ''
    BN = ''

    def __init__(self, event: Event):
        super().__init__(event)
        self.settings = SettingsSandbox('payment', 'paypal', event)

    @property
    def settings_form_fields(self):
        return {}

    @property
    def is_enabled(self) -> bool:
        if self.settings.connect_client_id and self.settings.connect_secret_key and not self.settings.secret:
            if not self.settings.isu_merchant_id:
                return False
        return self.settings.get('_enabled', as_type=bool) and self.settings.get('method_{}'.format(self.method),
                                                                                 as_type=bool)

    @property
    def test_mode_message(self):
        """
        Returns a message about the PayPal sandbox environment if the payment provider is configured in sandbox mode.

        Returns:
            str or None: Message about the PayPal sandbox environment, or None if not in sandbox mode.
        """
        if self.settings.connect_client_id and not self.settings.secret:
            is_sandbox = self.settings.connect_endpoint == 'sandbox'
        else:
            is_sandbox = self.settings.get('endpoint') == 'sandbox'

        if is_sandbox:
            return _(
                "The PayPal sandbox environment enables testing without actual money transactions. "
                "However, it requires a PayPal sandbox user account for logging in."
            )

        return None

    def is_allowed(self, request: HttpRequest, total: Decimal = None) -> bool:
        return super().is_allowed(request, total) and self.event.currency in SUPPORTED_CURRENCIES

    def init_api(self):
        """
        Initializes the PayPal API client based on the current settings for sandbox or live environment.

        Note:
            This method assumes that relevant settings (`connect_client_id`, `connect_secret_key`,
            `isu_merchant_id`, `endpoint`, etc.) are properly configured before calling `init_api()`.

        Raises:
            ValueError: If neither sandbox nor live endpoint configuration is found in the settings.

        """
        if self.settings.connect_client_id and not self.settings.secret:
            if 'sandbox' in self.settings.connect_endpoint:
                env = SandboxEnvironment(
                    client_id=self.settings.connect_client_id,
                    client_secret=self.settings.connect_secret_key,
                    merchant_id=self.settings.get('isu_merchant_id', None),
                    partner_id=self.BN
                )
            else:
                env = LiveEnvironment(
                    client_id=self.settings.connect_client_id,
                    client_secret=self.settings.connect_secret_key,
                    merchant_id=self.settings.get('isu_merchant_id', None),
                    partner_id=self.BN
                )
        else:
            if 'sandbox' in self.settings.get('endpoint'):
                env = SandboxEnvironment(
                    client_id=self.settings.get('client_id'),
                    client_secret=self.settings.get('secret'),
                    merchant_id=None,
                    partner_id=self.BN
                )
            else:
                env = LiveEnvironment(
                    client_id=self.settings.get('client_id'),
                    client_secret=self.settings.get('secret'),
                    merchant_id=None,
                    partner_id=self.BN
                )

        self.client = PayPalHttpClient(env)

    def payment_is_valid_session(self, request: HttpRequest):
        return request.session.get('payment_paypal_oid', '') != ''

    def payment_form_render(self, request) -> str:
        def build_kwargs():
            keys = ['organizer', 'event', 'order', 'secret', 'cart_namespace']
            kwargs = {}
            for key in keys:
                if key in request.resolver_match.kwargs:
                    kwargs[key] = request.resolver_match.kwargs[key]
            return kwargs

        @scopes_disabled()
        def count_known_failures():
            return OrderPayment.objects.filter(
                provider="paypal", info__contains="RESOURCE_NOT_FOUND", created__gt=now() - timedelta(hours=2)
            ).count()

        known_issue_failures = cache.get_or_set(
            'paypal_known_issue_failures',
            count_known_failures(),
            600
        )

        template = get_template('plugins/paypal/checkout_payment_form.html')
        ctx = {
            'request': request,
            'event': self.event,
            'settings': self.settings,
            'method': self.method,
            'known_issue': known_issue_failures > 1,
            'xhr': eventreverse(self.event, 'plugins:paypal:xhr', kwargs=build_kwargs())
        }
        return template.render(ctx)

    def checkout_prepare(self, request, cart):
        """
        Prepares for checkout by verifying the status of a PayPal order associated with the current session.

        Checks if the PayPal order ID matches the one stored in the session. If so, initializes the PayPal API client,
        retrieves the order status, and verifies if the order is approved. Returns True if approved, False otherwise.

        Args:
            request (HttpRequest): The HTTP request object.
            cart: The cart or order object being processed.

        Returns:
            bool: True if the PayPal order is approved and ready for checkout, False otherwise.

        """
        paypal_order_id = request.POST.get('payment_paypal_{}_oid'.format(self.method))

        if not paypal_order_id:
            messages.warning(request, _('You may need to enable JavaScript for PayPal payments.'))
            return False

        if paypal_order_id != request.session.get('payment_paypal_oid'):
            messages.warning(request, _('We had trouble communicating with PayPal.'))
            return False

        self.init_api()

        try:
            req = OrdersGetRequest(paypal_order_id)
            response = self.client.execute(req)
        except IOError as e:
            if "RESOURCE_NOT_FOUND" in str(e):
                messages.warning(request, _(
                    'Your payment failed due to a known issue within PayPal. '
                    'Please retry or use another payment method.'
                ))
            else:
                messages.warning(request, _('We had trouble communicating with PayPal.'))
            logger.exception('PayPal OrdersGetRequest({}): {}'.format(paypal_order_id, str(e)))
            return False

        if response.result.status == 'APPROVED':
            return True
        else:
            messages.warning(request, _('Something went wrong when verifying the payment status. Please try again.'))
            return False

    def format_price(self, value):
        """
        Format the given value to a string representation rounded to the nearest whole number for specific currencies.

        Args:
            value (decimal.Decimal or float): The value to be formatted.

        Returns:
            str: The formatted price as a string.

        """
        zero_decimals_currencies = {
            'HUF', 'JPY', 'MYR', 'TWD', 'CLP', 'BIF', 'DJF', 'GNF', 'KMF',
            'KRW', 'LAK', 'PYG', 'RWF', 'UGX', 'VND', 'VUV', 'XAF', 'XOF', 'XPF'
        }

        # Determine currency from event or default if not provided
        currency = self.event.currency

        if currency in zero_decimals_currencies:
            return str(round_decimal(value, currency, 0))
        else:
            return str(round_decimal(value, currency))

    @property
    def abort_pending_allowed(self):
        return False

    def create_paypal_order(self, request, payment=None, cart_total=None):
        """
        Create a PayPal order for either a specific payment or a cart total.

        Args:
            request (HttpRequest): The HTTP request object.
            payment (OrderPayment, optional): The specific payment to create an order for. Defaults to None.
            cart_total (decimal.Decimal, optional): The total amount for the cart if no specific payment is provided. Defaults to None.

        Returns:
            dict or None: The PayPal order response if successful, None otherwise.

        Raises:
            PaymentException: If there is a misconfiguration in the payment method settings.

        """
        self.init_api()

        kwargs = {}
        if request.resolver_match and 'cart_namespace' in request.resolver_match.kwargs:
            kwargs['cart_namespace'] = request.resolver_match.kwargs['cart_namespace']

        if self.settings.connect_client_id and self.settings.connect_secret_key and not self.settings.secret:
            if request.event.settings.payment_paypal_isu_merchant_id:
                payee = {
                    "merchant_id": request.event.settings.payment_paypal_isu_merchant_id,
                }
            else:
                raise PaymentException('Payment method misconfigured')
        else:
            payee = {}

        if payment and not cart_total:
            value = self.format_price(payment.amount)
            currency = payment.order.event.currency
            description = '{prefix}{orderstring}{postfix}'.format(
                prefix='{} '.format(self.settings.prefix) if self.settings.prefix else '',
                orderstring=__('Order {order} for {event}').format(
                    event=request.event.name,
                    order=payment.order.code
                ),
                postfix=' {}'.format(self.settings.postfix) if self.settings.postfix else ''
            )
            custom_id = '{prefix}{slug}-{code}{postfix}'.format(
                prefix='{} '.format(self.settings.prefix) if self.settings.prefix else '',
                slug=self.event.slug.upper(),
                code=payment.order.code,
                postfix=' {}'.format(self.settings.postfix) if self.settings.postfix else ''
            )
            request.session['payment_paypal_payment'] = payment.pk
        elif cart_total and not payment:
            value = self.format_price(cart_total)
            currency = request.event.currency
            description = __('Event tickets for {event}').format(event=request.event.name)
            custom_id = '{prefix}{slug}{postfix}'.format(
                prefix='{} '.format(self.settings.prefix) if self.settings.prefix else '',
                slug=request.event.slug.upper(),
                postfix=' {}'.format(self.settings.postfix) if self.settings.postfix else ''
            )
            request.session['payment_paypal_payment'] = None
        else:
            return None

        try:
            paymentreq = OrdersCreateRequest()
            paymentreq.request_body({
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'amount': {
                        'currency_code': currency,
                        'value': value,
                    },
                    'payee': payee,
                    'description': description[:127],
                    'custom_id': custom_id[:127],
                }],
                'application_context': {
                    'locale': request.LANGUAGE_CODE.split('-')[0],
                    'shipping_preference': 'NO_SHIPPING',
                    'user_action': 'CONTINUE',
                    'return_url': build_absolute_uri(request.event, 'plugins:paypal:return', kwargs=kwargs),
                    'cancel_url': build_absolute_uri(request.event, 'plugins:paypal:abort', kwargs=kwargs),
                },
            })
            response = self.client.execute(paymentreq)

            if payment:
                ReferencedPayPalObject.objects.get_or_create(order=payment.order, payment=payment,
                                                             reference=response.result.id)

        except IOError as e:
            if "RESOURCE_NOT_FOUND" in str(e):
                messages.error(request, _('Your payment has failed due to a known issue within PayPal. '
                                          'Please try again, as there is a high chance of success on a second '
                                          'or third attempt. Alternatively, you can try other available payment '
                                          'methods.'))
            else:
                messages.error(request, _('We had trouble communicating with PayPal'))
            logger.exception('PayPal OrdersCreateRequest: {}'.format(str(e)))
            return None

        else:
            if response.result.status not in ('CREATED', 'PAYER_ACTION_REQUIRED'):
                messages.error(request, _('We had trouble communicating with PayPal'))
                logger.error('Invalid payment state: ' + str(paymentreq))
                return None

            request.session['payment_paypal_oid'] = response.result.id
            return response.result

    def checkout_confirm_render(self, request) -> str:
        template = get_template('plugins/paypal/checkout_payment_confirm.html')
        ctx = {
            'request': request,
            'url': resolve(request.path_info),
            'event': self.event,
            'settings': self.settings,
            'method': self.method
        }
        return template.render(ctx)

    @transaction.atomic
    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        payment = OrderPayment.objects.select_for_update(of=OF_SELF).get(pk=payment.pk)
        if payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED:
            logger.warning('payment is already confirmed; possible return-view/webhook race-condition')
            return

        try:
            if request.session.get('payment_paypal_oid', '') == '':
                raise PaymentException(_('We were unable to process your payment. See below for details on how to '
                                         'proceed.'))

            if self.settings.connect_client_id and self.settings.connect_secret_key and not self.settings.secret:
                if not self.settings.isu_merchant_id:
                    raise PaymentException('Payment method misconfigured')
            self.init_api()
            paypal_oid = request.session.get('payment_paypal_oid')
            try:
                req = OrdersGetRequest(paypal_oid)
                response = self.client.execute(req)
            except IOError as e:
                logger.exception('PayPal OrdersGetRequest({}): {}'.format(paypal_oid, str(e)))
                payment.fail(info={
                    "error": {
                        "name": "IOError",
                        "message": str(e),
                        "order_id": paypal_oid,
                    }
                })
                if "RESOURCE_NOT_FOUND" in str(e):
                    raise PaymentException(_('Your payment has failed due to a known issue within PayPal.'
                                             ' Please try again, as there is a high chance of success on a'
                                             ' second or third attempt. Alternatively, you can try '
                                             'other available payment methods.'))
                raise PaymentException(_('We had trouble communicating with PayPal'))
            else:
                pp_captured_order = response.result

            try:
                ReferencedPayPalObject.objects.get_or_create(order=payment.order, payment=payment,
                                                             reference=pp_captured_order.id)
            except ReferencedPayPalObject.MultipleObjectsReturned:
                pass
            if Decimal(pp_captured_order.purchase_units[0].amount.value) != payment.amount or \
                    pp_captured_order.purchase_units[0].amount.currency_code != self.event.currency:
                logger.error(
                    'Value mismatch: Payment %s vs paypal trans %s' % (payment.id, str(pp_captured_order.dict())))
                payment.fail(info={
                    "error": {
                        "name": "ValidationError",
                        "message": "Value mismatch",
                    }
                })
                raise PaymentException(_('We were unable to process your payment. See below for details on how to '
                                         'proceed.'))

            if pp_captured_order.status == 'APPROVED':
                if payment.order.code not in pp_captured_order.purchase_units[0].custom_id:
                    try:
                        custom_id = '{prefix}{orderstring}{postfix}'.format(
                            prefix='{} '.format(self.settings.prefix) if self.settings.prefix else '',
                            orderstring=__('Order {slug}-{code}').format(
                                slug=self.event.slug.upper(),
                                code=payment.order.code
                            ),
                            postfix=' {}'.format(self.settings.postfix) if self.settings.postfix else ''
                        )
                        description = '{prefix}{orderstring}{postfix}'.format(
                            prefix='{} '.format(self.settings.prefix) if self.settings.prefix else '',
                            orderstring=__('Order {order} for {event}').format(
                                event=request.event.name,
                                order=payment.order.code
                            ),
                            postfix=' {}'.format(self.settings.postfix) if self.settings.postfix else ''
                        )
                        patchreq = OrdersPatchRequest(pp_captured_order.id)
                        patchreq.request_body([
                            {
                                "op": "replace",
                                "path": "/purchase_units/@reference_id=='default'/custom_id",
                                "value": custom_id[:127],
                            },
                            {
                                "op": "replace",
                                "path": "/purchase_units/@reference_id=='default'/description",
                                "value": description[:127],
                            }
                        ])
                        self.client.execute(patchreq)
                    except IOError as e:
                        if "RESOURCE_NOT_FOUND" in str(e):
                            messages.error(request,
                                           _('Your payment has failed due to a known issue within PayPal. '
                                             'Please try again, as there is a high chance of success on a '
                                             'second or third attempt. Alternatively, '
                                             'you can try other available payment methods.'))
                        else:
                            messages.error(request, _('We had trouble communicating with PayPal'))
                        payment.fail(info={
                            "error": {
                                "name": "IOError",
                                "message": str(e),
                            },
                            "order_id": paypal_oid,
                        })
                        logger.exception('PayPal OrdersPatchRequest({}): {}'.format(paypal_oid, str(e)))
                        return

                try:
                    capturereq = OrdersCaptureRequest(pp_captured_order.id)
                    response = self.client.execute(capturereq)
                except HttpError as e:
                    text = _('We were unable to process your payment. See below for details on how to proceed.')
                    try:
                        error = json.loads(e.message)
                    except ValueError:
                        error = {"message": str(e.message)}

                    try:
                        if error["details"][0]["issue"] == "ORDER_ALREADY_CAPTURED":
                            logger.info('PayPal ORDER_ALREADY_CAPTURED, ignoring')
                            return
                        elif error["details"][0]["issue"] == "INSTRUMENT_DECLINED":
                            text = error["details"][0]["description"]
                    except (KeyError, IndexError):
                        pass

                    payment.fail(info={**pp_captured_order.dict(), "error": error}, log_data=error)
                    logger.exception('PayPal OrdersCaptureRequest({}): {}'.format(pp_captured_order.id, str(e)))
                    raise PaymentException(text)
                except IOError as e:
                    payment.fail(info={**pp_captured_order.dict(), "error": {"message": str(e)}},
                                 log_data={"error": str(e)})
                    logger.exception('PayPal OrdersCaptureRequest({}): {}'.format(pp_captured_order.id, str(e)))
                    if "RESOURCE_NOT_FOUND" in str(e):
                        raise PaymentException(
                            _('Your payment has failed due to a known issue within PayPal. '
                              'Please try again, as there is a high chance of success on a '
                              'second or third attempt. Alternatively, you can try other available payment methods.')
                        )
                    else:
                        raise PaymentException(_('We were unable to process your payment. '
                                                 'See below for details on how to proceed.'))
                else:
                    pp_captured_order = response.result

                for purchaseunit in pp_captured_order.purchase_units:
                    for capture in purchaseunit.payments.captures:
                        try:
                            ReferencedPayPalObject.objects.get_or_create(order=payment.order, payment=payment,
                                                                         reference=capture.id)
                        except ReferencedPayPalObject.MultipleObjectsReturned:
                            pass

                        if capture.status != 'COMPLETED':
                            messages.warning(request, _('PayPal has not yet approved the payment.'
                                                        ' We will inform you as soon as the payment is completed.'))
                            payment.info = json.dumps(pp_captured_order.dict())
                            payment.state = OrderPayment.PAYMENT_STATE_PENDING
                            payment.save()
                            return

            payment.refresh_from_db()

            if pp_captured_order.status != 'COMPLETED':
                payment.fail(info=pp_captured_order.dict())
                logger.error('Invalid state: %s' % repr(pp_captured_order.dict()))
                raise PaymentException(
                    _('We were unable to process your payment. See below for details on how to proceed.')
                )

            if payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED:
                logger.warning('PayPal success event even though order is already marked as paid')
                return

            try:
                payment.info = json.dumps(pp_captured_order.dict())
                payment.save(update_fields=['info'])
                payment.confirm()
            except Quota.QuotaExceededException as e:
                raise PaymentException(str(e))

            except SendMailException:
                messages.warning(request, _('There was an error sending the confirmation mail.'))
        finally:
            if 'payment_paypal_oid' in request.session:
                del request.session['payment_paypal_oid']

    def payment_pending_render(self, request, payment) -> str:
        retry = True
        try:
            if (
                    payment.info
                    and payment.info_data['purchase_units'][0]['payments']['captures'][0]['status'] == 'pending'
            ):
                retry = False
        except (KeyError, IndexError):
            pass

        error = payment.info_data.get("error", {})
        is_known_issue = error.get("name") == "RESOURCE_NOT_FOUND" or "RESOURCE_NOT_FOUND" in (
                error.get("message") or "")

        template = get_template('plugins/paypal/pending.html')
        ctx = {'request': request, 'event': self.event, 'settings': self.settings,
               'retry': retry, 'order': payment.order, 'is_known_issue': is_known_issue}
        return template.render(ctx)

    def matching_id(self, payment: OrderPayment):
        sale_id = None
        if 'purchase_units' not in payment.info_data:
            for trans in payment.info_data.get('transactions', []):
                for res in trans.get('related_resources', []):
                    if 'sale' in res and 'id' in res['sale']:
                        sale_id = res['sale']['id']
        else:
            for trans in payment.info_data.get('purchase_units', []):
                for res in trans.get('payments', {}).get('captures', []):
                    sale_id = res['id']

        return sale_id or payment.info_data.get('id', None)

    def api_payment_details(self, payment: OrderPayment):
        """
        Retrieves and formats PayPal payment details from an OrderPayment object.

        Args:
            payment (OrderPayment): The OrderPayment object containing payment details.

        Returns:
            dict: A dictionary containing formatted payment details:
                - 'payer_email': Payer's email address.
                - 'payer_id': Payer's PayPal ID.
                - 'cart_id': Cart ID associated with the payment.
                - 'payment_id': PayPal payment ID.
                - 'sale_id': PayPal sale ID.

        """
        sale_id = None

        # Legacy PayPal info-data structure
        if 'purchase_units' not in payment.info_data:
            for trans in payment.info_data.get('transactions', []):
                for res in trans.get('related_resources', []):
                    if 'sale' in res and 'id' in res['sale']:
                        sale_id = res['sale']['id']

            return {
                "payer_email": payment.info_data.get('payer', {}).get('payer_info', {}).get('email'),
                "payer_id": payment.info_data.get('payer', {}).get('payer_info', {}).get('payer_id'),
                "cart_id": payment.info_data.get('cart', None),
                "payment_id": payment.info_data.get('id', None),
                "sale_id": sale_id,
            }
        else:
            # Updated PayPal info-data structure
            for trans in payment.info_data.get('purchase_units', []):
                for res in trans.get('payments', {}).get('captures', []):
                    sale_id = res['id']

            return {
                "payer_email": payment.info_data.get('payer', {}).get('email_address'),
                "payer_id": payment.info_data.get('payer', {}).get('payer_id'),
                "cart_id": payment.info_data.get('id', None),
                "payment_id": sale_id,
                "sale_id": sale_id,
            }

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        if 'purchase_units' not in payment.info_data:
            template = get_template('plugins/paypal/control_legacy.html')
            sale_id = None
            for trans in payment.info_data.get('transactions', []):
                for res in trans.get('related_resources', []):
                    if 'sale' in res and 'id' in res['sale']:
                        sale_id = res['sale']['id']
            ctx = {'request': request, 'event': self.event, 'settings': self.settings,
                   'payment_info': payment.info_data, 'order': payment.order, 'sale_id': sale_id}
        else:
            template = get_template('plugins/paypal/control.html')
            ctx = {'request': request, 'event': self.event, 'settings': self.settings,
                   'payment_info': payment.info_data, 'order': payment.order}

        return template.render(ctx)

    def payment_control_render_short(self, payment: OrderPayment) -> str:
        if 'purchase_units' not in payment.info_data:
            return payment.info_data.get('payer', {}).get('payer_info', {}).get('email', '')
        else:
            return '{} / {}'.format(
                payment.info_data.get('id', ''),
                payment.info_data.get('payer', {}).get('email_address', '')
            )

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return (now() - payment.payment_date).days <= 180

    def payment_refund_supported(self, payment: OrderPayment):
        self.payment_partial_refund_supported(payment)

    def execute_refund(self, refund: OrderRefund):
        """
        Executes a refund for an OrderRefund object via PayPal.

        Args:
            refund (OrderRefund): The OrderRefund object containing refund details.

        Raises:
            PaymentException: If refunding the amount via PayPal fails.

        """
        self.init_api()  # Initialize PayPal API client

        try:
            pp_payment = None
            if "purchase_units" not in refund.payment.info_data:
                # Retrieve payment information if not already present
                req = OrdersGetRequest(refund.payment.info_data['cart'])
                response = self.client.execute(req)
                payment_info_data = response.result.dict()
            else:
                payment_info_data = refund.payment.info_data

            # Find a suitable payment ID for refunding
            for res in payment_info_data['purchase_units'][0]['payments']['captures']:
                if res['status'] in ['COMPLETED', 'PARTIALLY_REFUNDED']:
                    pp_payment = res['id']
                    break

            if not pp_payment:
                req = OrdersGetRequest(payment_info_data['id'])
                response = self.client.execute(req)
                for res in response.result.purchase_units[0].payments.captures:
                    if res['status'] in ['COMPLETED', 'PARTIALLY_REFUNDED']:
                        pp_payment = res.id
                        break

            # Execute the refund request
            req = CapturesRefundRequest(pp_payment)
            req.request_body({
                "amount": {
                    "value": self.format_price(refund.amount),
                    "currency_code": refund.order.event.currency
                }
            })
            response = self.client.execute(req)
        except HttpError as e:
            # Log refund failure and raise PaymentException
            refund.order.log_action('pretix.event.order.refund.failed', {
                'local_id': refund.local_id,
                'provider': refund.provider,
                'error': str(e)
            })
            logger.error('execute_refund: {}'.format(str(e)))
            raise PaymentException(_('Refunding the amount via PayPal failed: {}').format(str(e)))

        # Update refund information with PayPal response
        refund.info = json.dumps(response.result.dict())
        refund.save(update_fields=['info'])

        # Retrieve refund status
        req = RefundsGetRequest(response.result.id)
        response = self.client.execute(req)
        refund.info = json.dumps(response.result.dict())
        refund.save(update_fields=['info'])

        # Finalize refund status based on PayPal response
        if response.result.status == 'COMPLETED':
            refund.done()
        elif response.result.status == 'PENDING':
            refund.state = OrderRefund.REFUND_STATE_TRANSIT
            refund.save(update_fields=['state'])
        else:
            # Log refund failure and raise PaymentException
            refund.order.log_action('pretix.event.order.refund.failed', {
                'local_id': refund.local_id,
                'provider': refund.provider,
                'error': str(response.result.status_details.reason)
            })
            raise PaymentException(
                _('Refunding the amount via PayPal failed: {}').format(response.result.status_details.reason))

    def payment_prepare(self, request, payment):
        """
        Prepares the PayPal payment for approval.

        Args:
            request (HttpRequest): The HTTP request object.
            payment (OrderPayment): The OrderPayment object.

        Returns:
            bool: True if payment is successfully prepared and approved, False otherwise.
        """
        paypal_order_id = request.POST.get('payment_paypal_{}_oid'.format(self.method), None)

        if paypal_order_id and paypal_order_id == request.session.get('payment_paypal_oid', None):
            self.init_api()  # Initialize PayPal API client

            try:
                # Send request to PayPal to retrieve order status
                req = OrdersGetRequest(paypal_order_id)
                response = self.client.execute(req)
            except HttpError as e:
                if e.status_code == 404 and "RESOURCE_NOT_FOUND" in str(e):
                    messages.warning(
                        request,
                        _('Your payment has failed due to a known issue within PayPal. Please try again, '
                          'as there is a high chance of success on a second or third attempt. '
                          'Alternatively, you can try other available payment methods.')
                    )
                else:
                    messages.warning(request, _('We had trouble communicating with PayPal'))
                    logger.exception('PayPal OrdersGetRequest({}): {}'.format(paypal_order_id, str(e)))
                return False
            else:
                if response.result.status == 'APPROVED':
                    return True
                else:
                    messages.warning(request, _('Payment was not approved by PayPal. Please try again.'))
                    return False
        elif paypal_order_id:
            messages.warning(request, _('We had trouble communicating with PayPal'))
            return False
        else:
            messages.warning(request, _('You may need to enable JavaScript for PayPal payments.'))
            return False

    def shred_payment_info(self, obj: OrderPayment):
        """
        Shred sensitive payment information from the given OrderPayment object.
        """
        if obj.info:
            try:
                d = json.loads(obj.info)
                new = {
                    'id': d.get('id'),
                    'payer': {
                        'payer_info': {
                            'email': '█'  # Mask email address for privacy
                        }
                    },
                    'update_time': d.get('update_time'),
                    'transactions': [
                        {
                            'amount': t.get('amount')
                        } for t in d.get('transactions', [])
                    ],
                    '_shredded': True
                }
                obj.info = json.dumps(new)
                obj.save(update_fields=['info'])
            except json.JSONDecodeError:
                pass

        for le in obj.order.all_logentries().filter(action_type="pretix.plugins.paypal.event").exclude(data=""):
            try:
                d = json.loads(le.data)
                if 'resource' in d:
                    d['resource'] = {
                        'id': d['resource'].get('id'),
                        'sale_id': d['resource'].get('sale_id'),
                        'parent_payment': d['resource'].get('parent_payment'),
                    }
                le.data = json.dumps(d)
                le.shredded = True
                le.save(update_fields=['data', 'shredded'])
            except json.JSONDecodeError:
                pass

    def render_invoice_text(self, order: Order, payment: OrderPayment) -> str:
        """
        Render invoice text based on the order and payment information.

        Args:
            order (Order): The order object.
            payment (OrderPayment): The payment object associated with the order.

        Returns:
            str: Rendered invoice text.
        """
        if order.status == Order.STATUS_PAID:
            if payment.info_data.get('id', None):
                try:
                    return '{}\r\n{}: {}\r\n{}: {}'.format(
                        _('The payment for this invoice has already been received.'),
                        _('PayPal payment ID'),
                        payment.info_data['id'],
                        _('PayPal sale ID'),
                        payment.info_data['transactions'][0]['related_resources'][0]['sale']['id']
                    )
                except (KeyError, IndexError):
                    return '{}\r\n{}: {}'.format(
                        _('The payment for this invoice has already been received.'),
                        _('PayPal payment ID'),
                        payment.info_data['id']
                    )
            else:
                return super().render_invoice_text(order, payment)

        return self.settings.get('_invoice_text', as_type=LazyI18nString, default='')


class PaypalWallet(PaypalMethod):
    identifier = 'paypal'
    verbose_name = _('PayPal')
    public_name = _('PayPal')
    method = 'wallet'


class PaypalAPM(PaypalMethod):
    """
    PayPal Alternative Payment Methods (APM) integration.
    """

    identifier = 'paypal_apm'
    verbose_name = _('PayPal APM')
    public_name = _('PayPal Alternative Payment Methods')
    method = 'apm'

    def payment_is_valid_session(self, request):
        """
        Checks if the payment session is valid.
        """
        return True  # Replace with actual logic as needed

    def checkout_prepare(self, request, cart):
        """
        Prepares for the checkout process.
        """
        return True  # Replace with actual logic as needed

    def payment_prepare(self, request, payment):
        """
        Prepares for the payment process.
        """
        return True  # Replace with actual logic as needed

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        """
        Executes the payment process.
        """
        payment.provider = "paypal"
        payment.save(update_fields=["provider"])

        paypal_order = self.create_paypal_order(request, payment, None)
        if not paypal_order:
            raise PaymentException(_('We had trouble communicating with PayPal'))

        payment.info = json.dumps(paypal_order.dict())
        payment.save(update_fields=['info'])

        return eventreverse(self.event, 'plugins:paypal:pay', kwargs={
            'order': payment.order.code,
            'payment': payment.pk,
            'hash': payment.order.tagged_secret('plugins:paypal:pay'),
        })
