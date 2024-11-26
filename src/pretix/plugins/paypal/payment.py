import json
import logging
import urllib.parse
from collections import OrderedDict
from decimal import Decimal
from typing import Union

from django import forms
from django.contrib import messages
from django.core import signing
from django.http import HttpRequest
from django.template.loader import get_template
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.utils.translation import gettext as __, gettext_lazy as _
from i18nfield.strings import LazyI18nString

from pretix.base.decimal import round_decimal
from pretix.base.models import Event, Order, OrderPayment, OrderRefund, Quota
from pretix.base.payment import BasePaymentProvider, PaymentException
from pretix.base.services.mail import SendMailException
from pretix.base.settings import SettingsSandbox
from pretix.helpers.urls import build_absolute_uri as build_global_uri
from pretix.multidomain.urlreverse import build_absolute_uri
from pretix.plugins.paypal.models import ReferencedPayPalObject
from pretix.plugins.paypal.paypal_rest import PaypalRequestHandler

logger = logging.getLogger("pretix.plugins.paypal")

SUPPORTED_CURRENCIES = [
    "AUD",
    "BRL",
    "CAD",
    "CZK",
    "DKK",
    "EUR",
    "HKD",
    "HUF",
    "INR",
    "ILS",
    "JPY",
    "MYR",
    "MXN",
    "TWD",
    "NZD",
    "NOK",
    "PHP",
    "PLN",
    "GBP",
    "RUB",
    "SGD",
    "SEK",
    "CHF",
    "THB",
    "USD",
]

LOCAL_ONLY_CURRENCIES = ["INR"]


class Paypal(BasePaymentProvider):
    identifier = "paypal"
    verbose_name = _("PayPal")
    payment_form_fields = OrderedDict([])

    def __init__(self, event: Event):
        super().__init__(event)
        self.settings = SettingsSandbox("payment", "paypal", event)
        self.paypal_request_handler = PaypalRequestHandler(self.settings)

    @property
    def test_mode_message(self):
        if self.settings.connect_client_id and not self.settings.secret:
            # in OAuth mode, sandbox mode needs to be set global
            is_sandbox = self.settings.connect_endpoint == "sandbox"
        else:
            is_sandbox = self.settings.get("endpoint") == "sandbox"
        if is_sandbox:
            return _(
                "The PayPal sandbox is being used, you can test without actually sending money but you will need a "
                "PayPal sandbox user to log in."
            )
        return None

    @property
    def settings_form_fields(self):
        if self.settings.connect_client_id and not self.settings.secret:
            # PayPal connect
            if self.settings.connect_user_id:
                fields = [
                    (
                        "connect_user_id",
                        forms.CharField(label=_("PayPal account"), disabled=True),
                    ),
                ]
            else:
                return {}
        else:
            fields = [
                (
                    "client_id",
                    forms.CharField(
                        label=_("Client ID"),
                        max_length=80,
                        min_length=80,
                        help_text=_(
                            '<a target="_blank" rel="noopener" href="{docs_url}">{text}</a>'
                        ).format(
                            text=_(
                                "Click here for a tutorial on how to obtain the required keys"
                            ),
                            docs_url="https://docs.eventyay.com/en/latest/user/payments/paypal.html",
                        ),
                    ),
                ),
                (
                    "secret",
                    forms.CharField(
                        label=_("Secret"),
                        max_length=80,
                        min_length=80,
                    ),
                ),
                (
                    "endpoint",
                    forms.ChoiceField(
                        label=_("Endpoint"),
                        initial="live",
                        choices=(
                            ("live", "Live"),
                            ("sandbox", "Sandbox"),
                        ),
                    ),
                ),
                (
                    "webhook_id",
                    forms.CharField(
                        label=_("Webhook ID"),
                        max_length=20,
                        min_length=10,
                    ),
                )
            ]

        extra_fields = [
            (
                "prefix",
                forms.CharField(
                    label=_("Reference prefix"),
                    help_text=_(
                        "Any value entered here will be added in front of the regular booking reference "
                        "containing the order number."
                    ),
                    required=False,
                ),
            )
        ]

        d = OrderedDict(
            fields + extra_fields + list(super().settings_form_fields.items())
        )

        d.move_to_end("prefix")
        d.move_to_end("_enabled", False)
        return d

    def get_connect_url(self, request):
        """
        Generate link for button Connect to Paypal in payment setting
        """
        request.session["payment_paypal_oauth_event"] = request.event.pk
        request.session["payment_paypal_tracking_id"] = get_random_string(111)

        response_data = self.paypal_request_handler.create_partner_referrals(
            data={
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
                                        "ACCESS_MERCHANT_INFORMATION",
                                    ],
                                },
                            }
                        },
                    }
                ],
                "products": ["EXPRESS_CHECKOUT"],
                "partner_config_override": {
                    "return_url": build_global_uri("plugins:paypal:oauth.return")
                },
                "legal_consents": [{"type": "SHARE_DATA_CONSENT", "granted": True}],
                "tracking_id": request.session["payment_paypal_tracking_id"]
            },
        )

        if response_data.get("errors"):
            errors = response_data.get("errors")
            messages.error(
                request,
                _("An error occurred during connecting with PayPal: {}").format(
                    errors["reason"]
                ),
            )
            return

        response = response_data.get("response")
        for link in response["links"]:
            if link["rel"] == "action_url":
                return link["href"]

    def settings_content_render(self, request):
        settings_content = ""
        if self.settings.connect_client_id and not self.settings.secret:
            # Use PayPal connect
            if not self.settings.connect_user_id:
                settings_content = (
                    "<p>{}</p>" "<a href='{}' class='btn btn-primary btn-lg'>{}</a>"
                ).format(
                    _(
                        "To accept payments via PayPal, you will need an account at PayPal. By clicking on the "
                        "following button, you can either create a new PayPal account connect Eventyay to an existing "
                        "one."
                    ),
                    self.get_connect_url(request),
                    _("Connect with {icon} PayPal").format(
                        icon='<i class="fa fa-paypal"></i>'
                    ),
                )
            else:
                settings_content = (
                    "<button formaction='{}' class='btn btn-danger'>{}</button>"
                ).format(
                    reverse(
                        "plugins:paypal:oauth.disconnect",
                        kwargs={
                            "organizer": self.event.organizer.slug,
                            "event": self.event.slug,
                        },
                    ),
                    _("Disconnect from PayPal"),
                )
        else:
            settings_content = "<div class='alert alert-info'>%s<br /><code>%s</code></div>" % (
                _(
                    "Please configure a PayPal Webhook to the following endpoint in order to automatically cancel orders "
                    "when payments are refunded externally. And set webhook id to make it work properly."
                ),
                build_global_uri("plugins:paypal:webhook"),
            )

        if self.event.currency not in SUPPORTED_CURRENCIES:
            settings_content += (
                '<br><br><div class="alert alert-warning">%s '
                '<a href="https://developer.paypal.com/docs/api/reference/currency-codes/">%s</a>'
                "</div>"
            ) % (
                _("PayPal does not process payments in your event's currency."),
                _(
                    "Please check this PayPal page for a complete list of supported currencies."
                ),
            )

        if self.event.currency in LOCAL_ONLY_CURRENCIES:
            settings_content += '<br><br><div class="alert alert-warning">%s' "</div>" % (
                _(
                    "Your event's currency is supported by PayPal as a payment and balance currency for in-country "
                    "accounts only. This means, that the receiving as well as the sending PayPal account must have been "
                    "created in the same country and use the same currency. Out of country accounts will not be able to "
                    "send any payments."
                )
            )

        return settings_content

    def is_allowed(self, request: HttpRequest, total: Decimal = None) -> bool:
        return (
            super().is_allowed(request, total)
            and self.event.currency in SUPPORTED_CURRENCIES
        )

    def payment_is_valid_session(self, request):
        return (
            request.session.get("payment_paypal_order_id", "") != ""
            and request.session.get("payment_paypal_payer", "") != ""
        )

    def payment_form_render(self, request) -> str:
        template = get_template("pretixplugins/paypal/checkout_payment_form.html")
        ctx = {"request": request, "event": self.event, "settings": self.settings}
        return template.render(ctx)

    def checkout_prepare(self, request, cart):
        kwargs = {}
        if request.resolver_match and "cart_namespace" in request.resolver_match.kwargs:
            kwargs["cart_namespace"] = request.resolver_match.kwargs["cart_namespace"]

        payee = {}
        if self.settings.get('client_id') or self.settings.get('secret'):
            # In case organizer set their own info
            # Check undeleted infos and remove theme
            if request.event.settings.payment_paypal_connect_user_id:
                del request.event.settings.payment_paypal_connect_user_id
            if request.event.settings.payment_paypal_merchant_id:
                del request.event.settings.payment_paypal_merchant_id
        elif request.event.settings.payment_paypal_connect_user_id:
            payee = {
                "email_address": request.event.settings.payment_paypal_connect_user_id,
                "merchant_id": request.event.settings.payment_paypal_merchant_id,
            }

        order_response = self.paypal_request_handler.create_order(
            order_data={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "items": [
                            {
                                "name": (
                                    "{} ".format(self.settings.prefix)
                                    if self.settings.prefix
                                    else ""
                                )
                                + __("Order for %s") % str(request.event),
                                "quantity": "1",
                                "unit_amount": {
                                    "currency_code": request.event.currency,
                                    "value": self.format_price(cart["total"]),
                                },
                            }
                        ],
                        "amount": {
                            "currency_code": request.event.currency,
                            "value": self.format_price(cart["total"]),
                            "breakdown": {
                                "item_total": {
                                    "currency_code": request.event.currency,
                                    "value": self.format_price(cart["total"]),
                                }
                            },
                        },
                        "description": __("Event tickets for {event}").format(
                            event=request.event.name
                        ),
                        "payee": payee,
                    }
                ],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "payment_method_preference": "UNRESTRICTED",
                            "landing_page": "LOGIN",
                            "return_url": build_absolute_uri(
                                request.event, "plugins:paypal:return", kwargs=kwargs
                            ),
                            "cancel_url": build_absolute_uri(
                                request.event, "plugins:paypal:abort", kwargs=kwargs
                            ),
                        }
                    }
                },
            },
        )

        if order_response.get("errors"):
            errors = order_response.get("errors")
            messages.error(
                request,
                _("An error occurred during connecting with PayPal: {}").format(
                    errors["reason"],
                ),
            )
            return None

        order_created = order_response.get("response")
        request.session["payment_paypal_payment"] = None
        return self._create_order(request, order_created)

    def format_price(self, value):
        return str(
            round_decimal(
                value,
                self.event.currency,
                {
                    # PayPal behaves differently than Stripe in deciding what currencies have decimal places
                    # Source https://developer.paypal.com/docs/classic/api/currency_codes/
                    "HUF": 0,
                    "JPY": 0,
                    "MYR": 0,
                    "TWD": 0,
                    # However, CLPs are not listed there while PayPal requires us not to send decimal places there. WTF.
                    "CLP": 0,
                    # Let's just guess that the ones listed here are 0-based as well
                    # https://developers.braintreepayments.com/reference/general/currencies
                    "BIF": 0,
                    "DJF": 0,
                    "GNF": 0,
                    "KMF": 0,
                    "KRW": 0,
                    "LAK": 0,
                    "PYG": 0,
                    "RWF": 0,
                    "UGX": 0,
                    "VND": 0,
                    "VUV": 0,
                    "XAF": 0,
                    "XOF": 0,
                    "XPF": 0,
                },
            )
        )

    @property
    def abort_pending_allowed(self):
        return False

    def _create_order(self, request, order):
        if order["status"] not in ("CREATED", "PAYER_ACTION_REQUIRED"):
            messages.error(request, _("We had trouble communicating with PayPal"))
            logger.error("Invalid order state: " + str(order))
            return
        request.session["payment_paypal_order_id"] = order["id"]
        for link in order["links"]:
            if link["rel"] == "payer-action":
                if request.session.get("iframe_session", False):
                    signer = signing.Signer(salt="safe-redirect")
                    return (
                        build_absolute_uri(request.event, "plugins:paypal:redirect")
                        + "?url="
                        + urllib.parse.quote(signer.sign(link["href"]))
                    )
                else:
                    return str(link["href"])

    def checkout_confirm_render(self, request) -> str:
        """
        Returns the HTML that should be displayed when the user selected this provider
        on the 'confirm order' page.
        """
        template = get_template("pretixplugins/paypal/checkout_payment_confirm.html")
        ctx = {"request": request, "event": self.event, "settings": self.settings}
        return template.render(ctx)

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        order_id = request.session.get("payment_paypal_order_id", "")
        paypal_payer = request.session.get("payment_paypal_payer", "")
        if order_id == "" or paypal_payer == "":
            raise PaymentException(
                _(
                    "We were unable to process your payment. See below for details on how to "
                    "proceed."
                )
            )

        order_response = self.paypal_request_handler.get_order(order_id=order_id)
        if order_response.get("errors"):
            errors = order_response.get("errors")
            logger.error(
                "Unable to retrieve order {} from Paypal: {}".format(
                    order_id, errors["reason"]
                )
            )
            payment.fail(
                info={
                    "error": {
                        "name": errors["type"],
                        "message": errors["reason"],
                        "exception": errors["exception"],
                        "order_id": order_id,
                    }
                }
            )
            raise PaymentException(
                _(
                    "An error occurred while communicating with PayPal, please try again."
                )
            )

        order_detail = order_response.get("response")
        try:
            ReferencedPayPalObject.objects.get_or_create(
                order=payment.order, payment=payment, reference=order_id
            )
        except ReferencedPayPalObject.MultipleObjectsReturned:
            pass

        if (
            str(order_detail["purchase_units"][0]["amount"]["value"])
            != str(payment.amount)
            or order_detail["purchase_units"][0]["amount"]["currency_code"]
            != self.event.currency
        ):
            logger.error(
                "Value mismatch: Payment %s vs paypal trans %s"
                % (payment.id, str(order_detail))
            )
            payment.fail(
                info={
                    "error": {
                        "name": "ValidationError",
                        "message": "Value mismatch",
                    }
                }
            )
            raise PaymentException(
                _(
                    "We were unable to process your payment. See below for details on how to "
                    "proceed."
                )
            )

        if order_detail["status"] == "APPROVED":
            description = (
                "{} ".format(self.settings.prefix) if self.settings.prefix else ""
            ) + __("Order {order} for {event}").format(
                event=request.event.name, order=payment.order.code
            )

            update_reponse = self.paypal_request_handler.update_order(
                order_id=order_id,
                update_data=[
                    {
                        "op": "replace",
                        "path": "/purchase_units/@reference_id=='default'/description",
                        "value": description,
                    }
                ],
            )
            if update_reponse.get("errors"):
                errors = update_reponse.get("errors")
                logger.error(
                    "Unable to patch order {} in Paypal: {}".format(
                        order_id, errors["reason"]
                    )
                )
                payment.fail(
                    info={
                        "error": {
                            "name": errors["type"],
                            "message": errors["reason"],
                            "exception": errors["exception"],
                            "order_id": order_id,
                        },
                    }
                )
                raise PaymentException(_("Unable to process your payment with Paypal"))

            capture_response = self.paypal_request_handler.capture_order(
                order_id=order_id
            )
            if capture_response.get("errors"):
                errors = update_reponse.get("errors")
                logger.error(
                    "Unable to capture order {} in Paypal: {}".format(
                        order_id, errors["reason"]
                    )
                )
                payment.fail(
                    info={
                        "error": {
                            "name": errors["type"],
                            "message": errors["reason"],
                            "exception": errors["exception"],
                            "order_id": order_id,
                        },
                    }
                )
                raise PaymentException(_("Unable to process your payment with Paypal"))

            captured_order = capture_response.get("response")
            for purchase_unit in captured_order["purchase_units"]:
                for capture in purchase_unit["payments"]["captures"]:
                    try:
                        ReferencedPayPalObject.objects.get_or_create(
                            order=payment.order,
                            payment=payment,
                            reference=capture["id"],
                        )
                    except ReferencedPayPalObject.MultipleObjectsReturned:
                        pass

                    if capture["status"] != "COMPLETED":
                        messages.warning(
                            request,
                            _(
                                "PayPal has not yet approved the payment. We will inform you as "
                                "soon as the payment completed."
                            ),
                        )
                        payment.info = json.dumps(captured_order)
                        payment.state = OrderPayment.PAYMENT_STATE_PENDING
                        payment.save()
                        return

        payment.refresh_from_db()
        if captured_order["status"] != "COMPLETED":
            payment.fail(info=captured_order)
            logger.error("Invalid state: %s" % repr(captured_order))
            raise PaymentException(
                _(
                    "We were unable to process your payment. See below for details on how to proceed."
                )
            )

        if payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED:
            logger.warning(
                "PayPal success event even though order is already marked as paid"
            )
            return

        try:
            payment.info = json.dumps(captured_order)
            payment.save(update_fields=["info"])
            payment.confirm()
        except Quota.QuotaExceededException as e:
            raise PaymentException(str(e))

        except SendMailException:
            messages.warning(
                request, _("There was an error sending the confirmation mail.")
            )
        return None

    def payment_pending_render(self, request, payment) -> str:
        retry = True
        try:
            if (
                payment.info
                and payment.info_data["purchase_units"][0]["payments"]["captures"][0][
                    "status"
                ]
                == "pending"
            ):
                retry = False
        except KeyError:
            pass
        template = get_template("pretixplugins/paypal/pending.html")
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "retry": retry,
            "order": payment.order,
        }
        return template.render(ctx)

    def matching_id(self, payment: OrderPayment):
        order_id = None
        for trans in payment.info_data.get("purchase_units", []):
            for res in trans.get("payments", {}).get("captures", []):
                order_id = res["id"]
                break
        return order_id or payment.info_data.get("id", None)

    def api_payment_details(self, payment: OrderPayment):
        order_id = self.matching_id(payment)
        return {
            "payer_email": payment.info_data.get("payer", {})
            .get("payer_info", {})
            .get("email"),
            "payer_id": payment.info_data.get("payer", {})
            .get("payer_info", {})
            .get("payer_id"),
            "cart_id": payment.info_data.get("cart", None),
            "payment_id": payment.info_data.get("id", None),
            "sale_id": order_id,
        }

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretixplugins/paypal/control.html")
        order_id = self.matching_id(payment)
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "payment_info": payment.info_data,
            "order": payment.order,
            "sale_id": order_id,
        }
        return template.render(ctx)

    def payment_control_render_short(self, payment: OrderPayment) -> str:
        return payment.info_data.get("payer", {}).get("payer_info", {}).get("email", "")

    def payment_partial_refund_supported(self, payment: OrderPayment):
        # Paypal refunds are possible for 180 days after purchase:
        # https://www.paypal.com/lc/smarthelp/article/how-do-i-issue-a-refund-faq780#:~:text=Refund%20after%20180%20days%20of,PayPal%20balance%20of%20the%20recipient.
        return (now() - payment.payment_date).days <= 180

    def payment_refund_supported(self, payment: OrderPayment):
        self.payment_partial_refund_supported(payment)

    def execute_refund(self, refund: OrderRefund):
        payment_info_data = refund.payment.info_data

        capture_id = None
        for capture in payment_info_data["purchase_units"][0]["payments"]["captures"]:
            if capture["status"] in ["COMPLETED", "PARTIALLY_REFUNDED"]:
                capture_id = capture["id"]
                break

        refund_payment = self.paypal_request_handler.refund_payment(
            capture_id=capture_id,
            refund_data={
                "amount": {
                    "value": self.format_price(refund.amount),
                    "currency_code": refund.order.event.currency,
                }
            },
            merchant_id=self.event.settings.payment_paypal_merchant_id,
        )
        if refund_payment.get("errors"):
            errors = refund_payment.get("errors")
            logger.error("execute_refund: {}".format(errors["reason"]))
            refund.order.log_action(
                "pretix.event.order.refund.failed",
                {
                    "local_id": refund.local_id,
                    "provider": refund.provider,
                    "error": str(errors),
                },
            )
            raise PaymentException(
                _(
                    "An error occurred while communicating with PayPal, please try again."
                )
            )

        refund_payment_response = refund_payment.get("response")
        refund.info = json.dumps(refund_payment_response)
        refund.save(update_fields=["info"])

        refund_id = refund_payment_response["id"]
        refund_detail = self.paypal_request_handler.get_refund_detail(
            refund_id=refund_id,
            merchant_id=self.event.settings.payment_paypal_merchant_id,
        )

        if refund_detail.get("errors"):
            errors = refund_payment.get("errors")
            refund.order.log_action(
                "pretix.event.order.refund.failed",
                {
                    "local_id": refund.local_id,
                    "provider": refund.provider,
                    "error": str(errors),
                },
            )
            raise PaymentException(
                _(
                    "An error occurred while communicating with PayPal, please try again."
                )
            )

        refund_detail_response = refund_detail.get("response")

        refund.info = json.dumps(refund_detail_response)
        refund.save(update_fields=["info"])

        if refund_detail_response["status"] == "COMPLETED":
            refund.done()
        elif refund_detail_response["status"] == "PENDING":
            refund.state = OrderRefund.REFUND_STATE_TRANSIT
            refund.save(update_fields=["state"])
        else:
            refund.order.log_action(
                "pretix.event.order.refund.failed",
                {
                    "local_id": refund.local_id,
                    "provider": refund.provider,
                    "error": str(refund_detail_response["status_details"]["reason"]),
                },
            )
            raise PaymentException(
                _("Refunding the amount via PayPal failed: {}").format(
                    refund_detail_response["status_details"]["reason"]
                )
            )

    def payment_prepare(self, request, payment_obj):
        payee = {}
        if self.settings.get('client_id') or self.settings.get('secret'):
            # In case organizer set their own info
            # Check undeleted infos and remove theme
            if request.event.settings.payment_paypal_connect_user_id:
                del request.event.settings.payment_paypal_connect_user_id
            if request.event.settings.payment_paypal_merchant_id:
                del request.event.settings.payment_paypal_merchant_id
        elif request.event.settings.payment_paypal_connect_user_id:
            payee = {
                "email_address": request.event.settings.payment_paypal_connect_user_id,
                "merchant_id": request.event.settings.payment_paypal_merchant_id,
            }

        order_response = self.paypal_request_handler.create_order(
            order_data={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "items": [
                            {
                                "name": (
                                    "{} ".format(self.settings.prefix)
                                    if self.settings.prefix
                                    else ""
                                )
                                + __("Order for %s") % str(request.event),
                                "quantity": "1",
                                "unit_amount": {
                                    "currency_code": request.event.currency,
                                    "value": self.format_price(payment_obj.amount),
                                },
                            }
                        ],
                        "amount": {
                            "currency_code": request.event.currency,
                            "value": self.format_price(payment_obj.amount),
                            "breakdown": {
                                "item_total": {
                                    "currency_code": request.event.currency,
                                    "value": self.format_price(payment_obj.amount),
                                }
                            },
                        },
                        "description": __("Event tickets for {event}").format(
                            event=request.event.name
                        ),
                        "payee": payee,
                    }
                ],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "payment_method_preference": "UNRESTRICTED",
                            "landing_page": "LOGIN",
                            "return_url": build_absolute_uri(
                                request.event, "plugins:paypal:return"
                            ),
                            "cancel_url": build_absolute_uri(
                                request.event, "plugins:paypal:abort"
                            ),
                        }
                    }
                },
            },
        )

        if order_response.get("errors"):
            errors = order_response.get("errors")
            messages.error(
                request,
                _("An error occurred during connecting with PayPal: {}").format(
                    errors["reason"]
                ),
            )
            return None

        order_created = order_response.get("response")
        request.session["payment_paypal_payment"] = None
        return self._create_order(request, order_created)

    def shred_payment_info(self, obj: Union[OrderPayment, OrderRefund]):
        if obj.info_data:
            d = obj.info_data
            purchase_units = d.get("purchase_units", [])
            if purchase_units:
                purchase_units[0] = {"payments": purchase_units[0].get("payments", {})}
            new = {
                "id": d.get("id"),
                "payer": {"payer_info": {"email": "█"}},
                "update_time": d.get("update_time"),
                "purchase_units": purchase_units,
                "_shredded": True,
            }
            obj.info = json.dumps(new)
            obj.save(update_fields=["info"])

        for le in (
            obj.order.all_logentries()
            .filter(action_type="pretix.plugins.paypal.event")
            .exclude(data="")
        ):
            d = le.parsed_data
            if "resource" in d:
                d["resource"] = {
                    "id": d["resource"].get("id"),
                    "sale_id": d["resource"].get("sale_id"),
                    "parent_payment": d["resource"].get("parent_payment"),
                }
            le.data = json.dumps(d)
            le.shredded = True
            le.save(update_fields=["data", "shredded"])

    def render_invoice_text(self, order: Order, payment: OrderPayment) -> str:
        if order.status == Order.STATUS_PAID:
            if payment.info_data.get("id", None):
                try:
                    return "{}\r\n{}: {}\r\n{}: {}".format(
                        _("The payment for this invoice has already been received."),
                        _("PayPal payment ID"),
                        payment.info_data["id"],
                        _("PayPal order ID"),
                        payment.info_data["purchase_units"][0]["payments"]["captures"][
                            0
                        ]["id"],
                    )
                except (KeyError, IndexError):
                    return "{}\r\n{}: {}".format(
                        _("The payment for this invoice has already been received."),
                        _("PayPal payment ID"),
                        payment.info_data["id"],
                    )
            else:
                return super().render_invoice_text(order, payment)

        return self.settings.get("_invoice_text", as_type=LazyI18nString, default="")
