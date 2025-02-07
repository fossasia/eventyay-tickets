from django.http import JsonResponse
from django.views import View

from pretix.eventyay_common.tasks import (
    billing_invoice_notification, check_billing_status_for_warning,
    monthly_billing_collect, process_auto_billing_charge, retry_failed_payment,
)


class BillingInvoicePreview(View):

    def get(self, request, *args, **kwargs):
        """
        @summary: This view is using for trigger the billing invoice task testing only. Will be removed in production.
        @return: json message
        """
        if self.kwargs['task'] == 'invoice-collect':
            monthly_billing_collect()
        elif self.kwargs['task'] == 'invoice-notification':
            billing_invoice_notification()
        elif self.kwargs['task'] == 'invoice-charge':
            process_auto_billing_charge()
        elif self.kwargs['task'] == 'invoice-retry':
            retry_failed_payment()
        elif self.kwargs['task'] == 'invoice-warning':
            check_billing_status_for_warning()

        return JsonResponse({'status': 'success', 'message': 'success.'})
