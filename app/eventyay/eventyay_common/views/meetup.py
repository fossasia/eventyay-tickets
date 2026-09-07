import datetime
from decimal import Decimal
from typing import Any, Dict

import dateutil.rrule
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django_scopes import scope

from eventyay.base.models import (
    Order,
    OrderPayment,
)


def get_meetup_analytics_context(event, tz=None) -> Dict[str, Any]:
    """Compute analytics data for Meetup dashboards."""
    if tz is None:
        tz = timezone.get_current_timezone()

    start_date = timezone.localdate(timezone.now() - datetime.timedelta(days=30), timezone=tz)
    end_date = timezone.localdate(timezone=tz)
    since = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=tz)

    with scope(organizer=event.organizer):
        placed_qs = (
            Order.objects.filter(event=event, datetime__gte=since)
            .annotate(day=TruncDate('datetime', tzinfo=tz))
            .values('day')
            .annotate(cnt=Count('pk'))
            .order_by('day')
        )
        ordered_by_day = {row['day']: row['cnt'] for row in placed_qs}

        payment_day_qs = (
            OrderPayment.objects.filter(
                order__event=event,
                state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                payment_date__gte=since,
            )
            .annotate(day=TruncDate('payment_date', tzinfo=tz))
            .values('day')
            .annotate(
                cnt=Count('order', distinct=True),
                revenue=Sum('amount'),
            )
            .order_by('day')
        )
        paid_by_day = {}
        rev_by_day = {}
        for row in payment_day_qs:
            day = row['day']
            paid_by_day[day] = paid_by_day.get(day, 0) + row['cnt']
            rev_by_day[day] = row['revenue'] or Decimal('0.00')

        orders_over_time = []
        for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
            d_date = d.date()
            orders_over_time.append({
                'x': d_date.strftime('%Y-%m-%d'),
                'ordered': ordered_by_day.get(d_date, 0),
                'paid': paid_by_day.get(d_date, 0),
            })

        status_qs = (
            Order.objects.filter(event=event)
            .values('status')
            .annotate(cnt=Count('pk'))
        )
        label_map = dict(Order.STATUS_CHOICE)
        orders_by_status = [
            {'label': str(label_map.get(row['status'], row['status'])), 'value': row['cnt']}
            for row in status_qs
            if row['cnt'] > 0
        ]

        prior_revenue = (
            OrderPayment.objects.filter(
                order__event=event,
                state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                payment_date__lt=since,
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        )

        revenue_over_time = []
        cumulative_rev = prior_revenue
        for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
            d_date = d.date()
            cumulative_rev += rev_by_day.get(d_date, Decimal('0.00'))
            revenue_over_time.append({
                'x': d_date.strftime('%Y-%m-%d'),
                'revenue': float(cumulative_rev),
            })

        has_orders = event.orders.exists()

    return {
        'orders_over_time': orders_over_time,
        'orders_by_status': orders_by_status,
        'revenue_over_time': revenue_over_time,
        'has_orders': has_orders,
    }
