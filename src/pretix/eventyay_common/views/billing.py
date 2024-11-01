from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.shortcuts import get_object_or_404
from django.views import View

from pretix.base.models import BillingInvoice
from pretix.eventyay_common.billing_invoice import generate_invoice_pdf
from pretix.eventyay_common.tasks import monthly_billing_collect


class BillingInvoicePreview(View):

    def get(self, request, *args, **kwargs):
        event = kwargs.get('event')
        organizer = kwargs.get('organizer')
        monthly_billing_collect()
        today = datetime.today()
        first_day_of_current_month = today.replace(day=1)
        billing_month = (first_day_of_current_month - relativedelta(months=1)).date()
        billing_invoice = get_object_or_404(
            BillingInvoice,
            event__slug=event,
            organizer__slug=organizer,
            monthly_bill=billing_month
        )
        return generate_invoice_pdf(billing_invoice)
