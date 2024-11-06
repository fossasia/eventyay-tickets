import json
import logging
from datetime import datetime

import stripe
from django.db import DatabaseError
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django_scopes import scopes_disabled

from pretix.base.models import BillingInvoice
from pretix.control.stripe_utils import get_stripe_secret_key

logger = logging.getLogger(__name__)


@csrf_exempt
def stripe_webhook_view(request):
    stripe.api_key = get_stripe_secret_key()
    payload = request.body

    try:
        event = stripe.Event.construct_from(
            json.loads(payload), stripe.api_key
        )
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON payload in Stripe webhook: %s", str(e))
        return HttpResponse("Invalid payload", status=400)

    if event.type == 'payment_intent.succeeded':
        try:
            invoice_id = event.data.object.get('metadata', {}).get('invoice_id')
            if not invoice_id:
                logger.error("Missing invoice_id in Stripe webhook metadata")
                return HttpResponse("Missing invoice_id", status=400)
            with scopes_disabled():
                invoice_information_updated = BillingInvoice.objects.filter(
                    id=invoice_id,
                ).update(
                    status=BillingInvoice.STATUS_PAID,
                    paid_datetime=datetime.now(),
                    payment_method='stripe',
                    updated_at=datetime.now(),
                    reminder_enabled=False
                )
                if not invoice_information_updated:
                    logger.error("Invoice not found or already updated: %s", invoice_id)
                    return HttpResponse("Invoice not found or already updated", status=404)

                logger.info("Payment succeeded for invoice: %s", invoice_id)
        except BillingInvoice.DoesNotExist as e:
            logger.error("Invoice %s not found in database: %s", invoice_id, str(e))
            return HttpResponse("Invoice not found", status=404)
        except DatabaseError as e:
            logger.error("Database error updating invoice %s: %s", invoice_id, str(e))
            return HttpResponse("Database error", status=500)
    return HttpResponse(status=200)
