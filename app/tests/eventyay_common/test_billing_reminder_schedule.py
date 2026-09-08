from datetime import UTC, datetime
from decimal import Decimal

import pytest
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django_scopes import scope

from eventyay.base.models import BillingInvoice, Order
from eventyay.eventyay_common.tasks import collect_billing_invoice


def _last_month_start() -> datetime:
    today = datetime.now(UTC)
    first_day_of_current_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_day_of_current_month - relativedelta(months=1)


@pytest.mark.django_db
def test_billing_reminder_schedule_is_defined():
    assert settings.BILLING_REMINDER_SCHEDULE == [14, 28]


@pytest.mark.django_db
def test_collect_billing_invoice_stores_reminder_schedule(event):
    last_month_date = _last_month_start()
    order_time = last_month_date + relativedelta(days=5)

    with scope(organizer=event.organizer, event=event):
        Order.objects.create(
            event=event,
            code='BILL1',
            status=Order.STATUS_PAID,
            datetime=order_time,
            expires=order_time + relativedelta(days=7),
            total=Decimal('50.00'),
            locale='en',
        )

        result = collect_billing_invoice(event, last_month_date, Decimal('2.5'), None)

        invoice = BillingInvoice.objects.get(event=event, monthly_bill=last_month_date)

    assert result.status is True
    assert invoice.reminder_schedule == [14, 28]
