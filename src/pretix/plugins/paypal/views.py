import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib import messages
from django.core import signing
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_scopes import scopes_disabled

from pretix.base.models import Event, Order, OrderPayment, OrderRefund, Quota
from pretix.base.payment import PaymentException
from pretix.control.permissions import event_permission_required
from pretix.multidomain.urlreverse import eventreverse
from pretix.plugins.paypal.models import ReferencedPayPalObject
from pretix.plugins.paypal.payment import Paypal

logger = logging.getLogger("pretix.plugins.paypal")


@xframe_options_exempt
def redirect_view(request, *args, **kwargs):
    signer = signing.Signer(salt="safe-redirect")
    try:
        url = signer.unsign(request.GET.get("url", ""))
    except signing.BadSignature:
        return HttpResponseBadRequest("Invalid parameter")

    r = render(
        request,
        "pretixplugins/paypal/redirect.html",
        {
            "url": url,
        },
    )
    r._csp_ignore = True
    return r


@scopes_disabled()
def oauth_return(request, *args, **kwargs):
    """
    https://developer.paypal.com/docs/multiparty/seller-onboarding/before-payment/
    Reference for seller onboarding
    """
    required_params = [
        "merchantId",
        "merchantIdInPayPal",
        "permissionsGranted",
        "consentStatus",
        "isEmailConfirmed",
    ]
    required_session_params = [
        "payment_paypal_oauth_event",
        "payment_paypal_tracking_id",
    ]
    if any(p not in request.session for p in required_session_params) or any(
        p not in request.GET for p in required_params
    ):
        messages.error(
            request,
            _("An error occurred during connecting with PayPal, please try again."),
        )
        return redirect(reverse("control:index"))

    event = get_object_or_404(Event, pk=request.session["payment_paypal_oauth_event"])
    event.settings.payment_paypal_connect_user_id = request.GET.get("merchantId")
    event.settings.payment_paypal_merchant_id = request.GET.get("merchantIdInPayPal")

    messages.success(
        request,
        _(
            "Your PayPal account is now connected to Eventyay. You can change the settings in "
            "detail below."
        ),
    )

    return redirect(
        reverse(
            "control:event.settings.payment.provider",
            kwargs={
                "organizer": event.organizer.slug,
                "event": event.slug,
                "provider": "paypal",
            },
        )
    )


def success(request, *args, **kwargs):
    token = request.GET.get("token")
    payer = request.GET.get("PayerID")
    request.session["payment_paypal_token"] = token
    request.session["payment_paypal_payer"] = payer

    urlkwargs = {}
    if "cart_namespace" in kwargs:
        urlkwargs["cart_namespace"] = kwargs["cart_namespace"]

    if request.session.get("payment_paypal_payment"):
        payment = OrderPayment.objects.get(
            pk=request.session.get("payment_paypal_payment")
        )
    else:
        payment = None

    if request.session.get("payment_paypal_order_id", None):
        if payment:
            prov = Paypal(request.event)
            try:
                resp = prov.execute_payment(request, payment)
            except PaymentException as e:
                messages.error(request, str(e))
                urlkwargs["step"] = "payment"
                return redirect(
                    eventreverse(
                        request.event, "presale:event.checkout", kwargs=urlkwargs
                    )
                )
            if resp:
                return resp
    else:
        messages.error(request, _("Invalid response from PayPal received."))
        logger.error("Session did not contain payment_paypal_order_id")
        urlkwargs["step"] = "payment"
        return redirect(
            eventreverse(request.event, "presale:event.checkout", kwargs=urlkwargs)
        )

    if payment:
        return redirect(
            eventreverse(
                request.event,
                "presale:event.order",
                kwargs={"order": payment.order.code, "secret": payment.order.secret},
            )
            + ("?paid=yes" if payment.order.status == Order.STATUS_PAID else "")
        )
    else:
        urlkwargs["step"] = "confirm"
        return redirect(
            eventreverse(request.event, "presale:event.checkout", kwargs=urlkwargs)
        )


def abort(request, *args, **kwargs):
    messages.error(request, _("It looks like you canceled the PayPal payment"))

    if request.session.get("payment_paypal_payment"):
        payment = OrderPayment.objects.get(
            pk=request.session.get("payment_paypal_payment")
        )
    else:
        payment = None

    if payment:
        return redirect(
            eventreverse(
                request.event,
                "presale:event.order",
                kwargs={"order": payment.order.code, "secret": payment.order.secret},
            )
            + ("?paid=yes" if payment.order.status == Order.STATUS_PAID else "")
        )
    else:
        return redirect(
            eventreverse(
                request.event, "presale:event.checkout", kwargs={"step": "payment"}
            )
        )


@csrf_exempt
@require_POST
@scopes_disabled()
def webhook(request, *args, **kwargs):
    """
    https://developer.paypal.com/api/rest/webhooks/event-names/
    Webhook reference
    """
    event_body = request.body.decode("utf-8").strip()
    event_json = json.loads(event_body)

    if event_json["resource_type"] not in ("checkout-order", "refund", "capture"):
        return HttpResponse("Wrong resource type", status=200)

    if event_json["resource_type"] == "refund":
        payment_id = None
        for link in event_json["resource"]["links"]:
            if link["rel"] == "up":
                refund_url = link["href"]
                payment_id = refund_url.split("/")[-1]
                break
    else:
        payment_id = event_json["resource"]["id"]

    references = [payment_id]

    # For filtering reference, there are a lot of ids appear within json__event
    ref_order_id = (
        event_json["resource"]
        .get("supplementary_data", {})
        .get("related_ids", {})
        .get("order_id")
    )
    if ref_order_id:
        references.append(ref_order_id)

    # Grasp the corresponding RPO
    rpo = (
        ReferencedPayPalObject.objects.select_related("order", "order__event")
        .filter(reference__in=references)
        .first()
    )
    if rpo:
        event = rpo.order.event
    else:
        if hasattr(request, "event"):
            event = request.event
        else:
            return HttpResponse("Unable to detect event", status=200)

    prov = Paypal(event)

    # Verify signature
    required_headers = [
        "PAYPAL-AUTH-ALGO",
        "PAYPAL-CERT-URL",
        "PAYPAL-TRANSMISSION-ID",
        "PAYPAL-TRANSMISSION-SIG",
        "PAYPAL-TRANSMISSION-TIME",
    ]
    if not all(header in request.headers for header in required_headers):
        return HttpResponse(
            "Unable to get required headers to verify webhook signature", status=200
        )

    # Prevent replay attacks: check timestamp
    current_time = datetime.now(timezone.utc)
    transmission_time = datetime.isoformat(
        request.headers.get("PAYPAL-TRANSMISSION-TIME")
    )
    if current_time - transmission_time > timedelta(minutes=10):
        return HttpResponse(
            "Webhook timestamp is old.", status=200
        )

    verify_response = prov.paypal_request_handler.verify_webhook_signature(
        data={
            "auth_algo": request.headers.get("PAYPAL-AUTH-ALGO"),
            "transmission_id": request.headers.get("PAYPAL-TRANSMISSION-ID"),
            "cert_url": request.headers.get("PAYPAL-CERT-URL"),
            "transmission_sig": request.headers.get("PAYPAL-TRANSMISSION-SIG"),
            "transmission_time": request.headers.get("PAYPAL-TRANSMISSION-TIME"),
            "webhook_id": event.settings.payment_paypal_webhook_id,
            "webhook_event": event_json,
        }
    )

    if (
        verify_response.get("errors")
        or verify_response.get("response", {}).get("verification_status") == "FAILURE"
    ):
        errors = verify_response.get("errors")
        logger.error(
            "Unable to verify signature of webhook: {}".format(errors["reason"])
        )
        return HttpResponse("Unable to verify signature of webhook", status=200)

    if rpo and "id" in rpo.payment.info_data:
        payment_id = rpo.payment.info_data["id"]

    order_response = prov.paypal_request_handler.get_order(order_id=payment_id)
    if order_response.get("errors"):
        errors = order_response.get("errors")
        logger.error("Paypal error on webhook: {}".format(errors["reason"]))
        logger.exception("PayPal error on webhook. Event data: %s" % str(event_json))
        return HttpResponse("Order {} not found".format(payment_id), status=200)

    order_detail = order_response.get("response")

    if rpo and rpo.payment:
        payment = rpo.payment
    else:
        payments = OrderPayment.objects.filter(
            order__event=event, provider="paypal", info__icontains=order_detail["id"]
        )
        payment = None
        for p in payments:
            for capture in p.info_data["purchase_units"][0]["payments"]["captures"]:
                if (
                    capture["status"] in ["COMPLETED", "PARTIALLY_REFUNDED"]
                    and capture["id"] == order_detail["id"]
                ):
                    payment = p
                    break

    if not payment:
        return HttpResponse("Payment not found", status=200)

    payment.order.log_action("pretix.plugins.paypal.event", data=event_json)

    if payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED and order_detail[
        "status"
    ] in ("PARTIALLY_REFUNDED", "REFUNDED", "COMPLETED"):
        if event_json["resource_type"] == "refund":
            refund_response = prov.paypal_request_handler.get_refund_detail(
                refund_id=event_json["resource"]["id"],
                merchant_id=event.settings.payment_paypal_merchant_id,
            )

            if refund_response.get("errors"):
                errors = refund_response.get("errors")
                logger.error("Paypal error on webhook: {}".format(errors["reason"]))
                logger.exception(
                    "PayPal error on webhook. Event data: %s" % str(event_json)
                )
                return HttpResponse(
                    "Refund {} not found".format(event_json["resource"]["id"]),
                    status=200,
                )

            refund_detail = refund_response.get("response")

            known_refunds = {
                refund.info_data.get("id"): refund for refund in payment.refunds.all()
            }
            if refund_detail["id"] not in known_refunds:
                payment.create_external_refund(
                    amount=abs(Decimal(refund_detail["amount"]["value"])),
                    info=json.dumps(refund_detail),
                )
            elif (
                known_refunds.get(refund_detail["id"]).state
                in (OrderRefund.REFUND_STATE_CREATED, OrderRefund.REFUND_STATE_TRANSIT)
                and refund_detail["status"] == "COMPLETED"
            ):
                known_refunds.get(refund_detail["id"]).done()

            if (
                "seller_payable_breakdown" in refund_detail
                and "total_refunded_amount" in refund_detail["seller_payable_breakdown"]
            ):
                known_sum = payment.refunds.filter(
                    state__in=(
                        OrderRefund.REFUND_STATE_DONE,
                        OrderRefund.REFUND_STATE_TRANSIT,
                        OrderRefund.REFUND_STATE_CREATED,
                        OrderRefund.REFUND_SOURCE_EXTERNAL,
                    )
                ).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
                total_refunded_amount = Decimal(
                    refund_detail["seller_payable_breakdown"]["total_refunded_amount"][
                        "value"
                    ]
                )
                if known_sum < total_refunded_amount:
                    payment.create_external_refund(
                        amount=total_refunded_amount - known_sum
                    )
        elif order_detail["status"] == "REFUNDED":
            known_sum = payment.refunds.filter(
                state__in=(
                    OrderRefund.REFUND_STATE_DONE,
                    OrderRefund.REFUND_STATE_TRANSIT,
                    OrderRefund.REFUND_STATE_CREATED,
                    OrderRefund.REFUND_SOURCE_EXTERNAL,
                )
            ).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

            if known_sum < payment.amount:
                payment.create_external_refund(amount=payment.amount - known_sum)
    elif payment.state in (
        OrderPayment.PAYMENT_STATE_PENDING,
        OrderPayment.PAYMENT_STATE_CREATED,
        OrderPayment.PAYMENT_STATE_CANCELED,
        OrderPayment.PAYMENT_STATE_FAILED,
    ):
        if order_detail["status"] == "APPROVED":
            try:
                request.session["payment_paypal_order_id"] = payment.info_data.get("id")
                payment.payment_provider.execute_payment(request, payment)
            except PaymentException as e:
                logger.error(
                    "Error executing approved payment in webhook: payment not yet populated."
                )
                logger.exception(
                    "Unable to execute payment in webhook: {}".format(str(e))
                )
        elif order_detail["status"] == "COMPLETED":
            captured = False
            captures_completed = True
            for purchase_unit in order_detail["purchase_units"]:
                for capture in purchase_unit["payments"]["captures"]:
                    try:
                        ReferencedPayPalObject.objects.get_or_create(
                            order=payment.order,
                            payment=payment,
                            reference=capture["id"],
                        )
                    except ReferencedPayPalObject.MultipleObjectsReturned:
                        pass

                    if capture["status"] in (
                        "COMPLETED",
                        "REFUNDED",
                        "PARTIALLY_REFUNDED",
                    ):
                        captured = True
                    else:
                        captures_completed = False
            if captured and captures_completed:
                try:
                    payment.info = json.dumps(order_detail)
                    payment.save(update_fields=["info"])
                    payment.confirm()
                except Quota.QuotaExceededException:
                    pass

    return HttpResponse(status=200)


@event_permission_required("can_change_event_settings")
@require_POST
def oauth_disconnect(request, **kwargs):
    del request.event.settings.payment_paypal_connect_user_id
    del request.event.settings.payment_paypal_merchant_id
    request.event.settings.payment_paypal__enabled = False
    messages.success(request, _("Your PayPal account has been disconnected."))

    return redirect(
        reverse(
            "control:event.settings.payment.provider",
            kwargs={
                "organizer": request.event.organizer.slug,
                "event": request.event.slug,
                "provider": "paypal",
            },
        )
    )
