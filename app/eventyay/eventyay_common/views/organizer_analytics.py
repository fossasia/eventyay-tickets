import datetime
import json
from collections.abc import Mapping, Sequence
from typing import Any

import dateutil.rrule
from django.db.models import (
    Count,
    Exists,
    OuterRef,
    Q,
    Sum,
)
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from django.views.generic import TemplateView
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Checkin,
    CheckinList,
    Event,
    Order,
    OrganizerFollower,
    OrderPayment,
    OrderPosition,
    QueuedMail,
    Submission,
    SubmissionStates,
)
from eventyay.control.permissions import OrganizerPermissionRequiredMixin


class OrganizerAnalyticsView(OrganizerPermissionRequiredMixin, TemplateView):

    template_name = 'eventyay_common/organizers/dashboard.html'
    permission = None

    @staticmethod
    def _to_date(val):
        if not val:
            return None
        if isinstance(val, datetime.datetime):
            return val.date()
        if isinstance(val, datetime.date):
            return val
        if isinstance(val, str):
            try:
                return datetime.date.fromisoformat(val.split()[0])
            except (ValueError, IndexError):
                return None
        return None

    @staticmethod
    def _to_iso_date(val):
        d = OrganizerAnalyticsView._to_date(val)
        return d.isoformat() if d else ""

    @staticmethod
    def _attendance_date_labels(now: datetime.datetime, tz: datetime.tzinfo) -> tuple[str, ...]:
        end_date = timezone.localdate(now, timezone=tz)
        start_date = end_date - datetime.timedelta(days=29)
        return tuple(
            (start_date + datetime.timedelta(days=offset)).isoformat()
            for offset in range(30)
        )

    @staticmethod
    def _project_attendance(
        attendance_daily_by_event: Mapping[int, Mapping[str, Mapping[str, int]]],
        attendance_events: Sequence[Mapping[str, Any]],
        date_labels: Sequence[str],
        requested_event: str | None,
    ) -> dict[str, Any]:
        """Return a clean presentation payload for Attendance Trends."""
        selector_events = [
            {'id': event['id'], 'name': str(event['name'])}
            for event in attendance_events
            if event.get('id') in attendance_daily_by_event
        ]
        permitted_event_ids = {e['id'] for e in selector_events}

        if not requested_event:
            selected_event_id: int | str = ''
            selected_event_ids = permitted_event_ids
        else:
            try:
                req_id = int(requested_event)
            except (TypeError, ValueError):
                req_id = None
            if req_id in permitted_event_ids:
                selected_event_id = req_id
                selected_event_ids = {req_id}
            else:
                selected_event_id = ''
                selected_event_ids = set()

        series = []
        for day in date_labels:
            orders = 0
            registrations = 0
            for event_id in selected_event_ids:
                bucket = attendance_daily_by_event.get(event_id, {}).get(day, {})
                orders += bucket.get('orders', 0)
                registrations += bucket.get('registrations', 0)
            series.append({'x': day, 'orders': orders, 'registrations': registrations})

        return {
            'attendance_events': selector_events,
            'attendance_selected_event_id': selected_event_id,
            'attendance_over_time_json': json.dumps(series),
            'has_attendance': any(point['orders'] or point['registrations'] for point in series),
        }

    def _event_ids_for_orders(self):
        if not hasattr(self, '_cached_event_ids_for_orders'):
            self._cached_event_ids_for_orders = list(
                self.request.user.get_events_with_permission('can_view_orders', request=self.request)
                .filter(organizer=self.request.organizer)
                .values_list('pk', flat=True)
            )
        return self._cached_event_ids_for_orders

    def _event_ids_for_email_engagement(self):
        # QueuedMail belongs to CFP proposals and shares the can_change_submissions scope.
        return self._event_ids_for_proposals()

    def _get_email_engagement_data(self):
        event_ids = self._event_ids_for_email_engagement()
        if not event_ids:
            return {
                'email_engagement_rows': [],
                'has_email_engagement': False,
            }

        with scopes_disabled():
            rows = list(
                QueuedMail.objects.filter(event_id__in=event_ids)
                .values('event_id')
                .annotate(
                    sent_count=Count('pk', filter=Q(sent__isnull=False)),
                    queued_count=Count('pk', filter=Q(sent__isnull=True)),
                )
            )
            mail_event_ids = [row['event_id'] for row in rows]
            events_by_id = {
                e.pk: e for e in Event.objects.filter(pk__in=mail_event_ids).only('pk', 'name')
            }

        email_engagement_rows = [
            {
                'event_id': row['event_id'],
                'event_name': str(events_by_id[row['event_id']].name),
                'sent': row['sent_count'],
                'queued': row['queued_count'],
            }
            for row in rows
            if row['event_id'] in events_by_id
        ]
        email_engagement_rows.sort(key=lambda r: (r['event_name'], r['event_id']))
        return {
            'email_engagement_rows': email_engagement_rows,
            'has_email_engagement': bool(email_engagement_rows),
        }

    def _get_follower_growth_data(self):
        current_timezone = timezone.get_current_timezone()
        now = timezone.now()
        with scopes_disabled():
            followers = OrganizerFollower.objects.filter(organizer=self.request.organizer)
            weekly_rows = list(
                followers.annotate(period=TruncWeek('created', tzinfo=current_timezone))
                .values('period')
                .annotate(count=Count('pk'))
                .order_by('period')
            )
            monthly_rows = list(
                followers.annotate(period=TruncMonth('created', tzinfo=current_timezone))
                .values('period')
                .annotate(count=Count('pk'))
                .order_by('period')
            )

        follower_total = sum(row['count'] for row in weekly_rows)

        today_local = timezone.localdate(now, timezone=current_timezone)
        current_week_start = today_local - datetime.timedelta(days=today_local.weekday())
        current_month_start = today_local.replace(day=1)

        weekly_by_date = {
            self._to_date(row['period']): row['count']
            for row in weekly_rows
            if row['period']
        }
        followers_weekly = []
        if weekly_by_date:
            min_week = min(weekly_by_date.keys())
            start_week = max(min_week, current_week_start - datetime.timedelta(weeks=11))
            for d in dateutil.rrule.rrule(dateutil.rrule.WEEKLY, dtstart=start_week, until=current_week_start):
                dt_key = d.date()
                followers_weekly.append({
                    'x': dt_key.isoformat(),
                    'y': weekly_by_date.get(dt_key, 0)
                })

        monthly_by_date = {
            self._to_date(row['period']): row['count']
            for row in monthly_rows
            if row['period']
        }
        followers_monthly = []
        if monthly_by_date:
            min_month = min(monthly_by_date.keys())
            if current_month_start.month <= 11:
                default_start_month = datetime.date(current_month_start.year - 1, current_month_start.month + 1, 1)
            else:
                default_start_month = datetime.date(current_month_start.year, 1, 1)
            start_month = max(min_month, default_start_month)
            for d in dateutil.rrule.rrule(dateutil.rrule.MONTHLY, dtstart=start_month, until=current_month_start):
                dt_key = d.date()
                followers_monthly.append({
                    'x': dt_key.isoformat(),
                    'y': monthly_by_date.get(dt_key, 0)
                })

        return {
            'follower_total': follower_total,
            'followers_weekly_json': json.dumps(followers_weekly),
            'followers_monthly_json': json.dumps(followers_monthly),
            'has_followers': bool(follower_total),
        }

    def _get_attendance_event_options(self):
        event_ids = self._event_ids_for_orders()
        if not event_ids:
            return []

        with scopes_disabled():
            events = list(Event.objects.filter(pk__in=event_ids).only('pk', 'name'))

        return sorted(
            ({'id': event.pk, 'name': str(event.name)} for event in events),
            key=lambda event: event['name'],
        )

    def _get_attendance_data(self):
        event_ids = self._event_ids_for_orders()
        if not event_ids:
            return {
                'attendance_daily_by_event': {},
                'attendance_events': [],
            }

        current_timezone = timezone.get_current_timezone()
        now = timezone.now()
        date_labels = self._attendance_date_labels(now, current_timezone)
        start_date = datetime.date.fromisoformat(date_labels[0])
        end_date = datetime.date.fromisoformat(date_labels[-1]) + datetime.timedelta(days=1)
        start = timezone.make_aware(
            datetime.datetime.combine(start_date, datetime.time.min),
            current_timezone,
        )
        end = timezone.make_aware(
            datetime.datetime.combine(end_date, datetime.time.min),
            current_timezone,
        )
        daily_by_event = {
            event_id: {
                date_label: {'orders': 0, 'registrations': 0}
                for date_label in date_labels
            }
            for event_id in event_ids
        }

        with scopes_disabled():
            orders_by_day = list(
                Order.objects.filter(
                    event_id__in=event_ids,
                    status__in=[Order.STATUS_PAID, Order.STATUS_PENDING],
                    datetime__gte=start,
                    datetime__lt=end,
                )
                .annotate(day=TruncDate('datetime', tzinfo=current_timezone))
                .values('event_id', 'day')
                .annotate(count=Count('pk'))
                .order_by('event_id', 'day')
            )
            registrations_by_day = list(
                OrderPosition.objects.filter(
                    order__event_id__in=event_ids,
                    order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING],
                    order__datetime__gte=start,
                    order__datetime__lt=end,
                )
                .annotate(day=TruncDate('order__datetime', tzinfo=current_timezone))
                .values('order__event_id', 'day')
                .annotate(count=Count('pk'))
                .order_by('order__event_id', 'day')
            )

        for row in orders_by_day:
            date_label = self._to_iso_date(row['day'])
            bucket = daily_by_event.get(row['event_id'], {}).get(date_label)
            if bucket is not None:
                bucket['orders'] = row['count']
        for row in registrations_by_day:
            date_label = self._to_iso_date(row['day'])
            bucket = daily_by_event.get(row['order__event_id'], {}).get(date_label)
            if bucket is not None:
                bucket['registrations'] = row['count']

        return {
            'attendance_daily_by_event': daily_by_event,
            'attendance_events': self._get_attendance_event_options(),
        }

    def _event_ids_for_proposals(self):
        if not hasattr(self, '_cached_event_ids_for_proposals'):
            self._cached_event_ids_for_proposals = list(
                self.request.user.get_events_with_permission('can_change_submissions', request=self.request)
                .filter(organizer=self.request.organizer)
                .values_list('pk', flat=True)
            )
        return self._cached_event_ids_for_proposals

    def _event_ids_for_checkins(self):
        if not hasattr(self, '_cached_event_ids_for_checkins'):
            self._cached_event_ids_for_checkins = list(
                self.request.user.get_events_with_permission('can_checkin_orders', request=self.request)
                .filter(organizer=self.request.organizer)
                .values_list('pk', flat=True)
            )
        return self._cached_event_ids_for_checkins

    def _get_tickets_data(self):
        event_ids = self._event_ids_for_orders()
        if not event_ids:
            return {
                'orders_over_time_json': '[]',
                'orders_by_status_json': '[]',
                'revenue_over_time_json': '[]',
                'currencies_json': '[]',
                'top_events': [],
                'has_orders': False,
            }

        tz = timezone.get_current_timezone()
        since = timezone.now() - datetime.timedelta(days=30)

        with scopes_disabled():
            placed_qs = (
                Order.objects.filter(event_id__in=event_ids, datetime__gte=since)
                .annotate(day=TruncDate('datetime', tzinfo=tz))
                .values('day')
                .annotate(cnt=Count('pk'))
                .order_by('day')
            )
            ordered_by_day = {self._to_date(row['day']): row['cnt'] for row in placed_qs}

            payment_day_qs = (
                OrderPayment.objects.filter(
                    order__event_id__in=event_ids,
                    state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                    payment_date__gte=since,
                )
                .annotate(day=TruncDate('payment_date', tzinfo=tz))
                .values('day', 'order__event__currency')
                .annotate(
                    cnt=Count('order', distinct=True),
                    revenue=Sum('amount')
                )
                .order_by('day')
            )
            payment_data = list(payment_day_qs)
            paid_by_day = {}
            rev_by_day = {}
            currencies = set()
            for row in payment_data:
                day = self._to_date(row['day'])
                currency = row['order__event__currency']
                paid_by_day[day] = paid_by_day.get(day, 0) + row['cnt']
                currencies.add(currency)
                day_revenue = rev_by_day.setdefault(day, {})
                day_revenue[currency] = float(row['revenue'] or 0)

            status_qs = (
                Order.objects.filter(event_id__in=event_ids)
                .values('status')
                .annotate(cnt=Count('pk'))
            )
            status_rows = list(status_qs)

            top_qs = list(
                Order.objects.filter(event_id__in=event_ids)
                .values('event')
                .annotate(
                    total_orders=Count('pk'),
                    paid_orders=Count('pk', filter=Q(status=Order.STATUS_PAID)),
                )
                .order_by('-total_orders')[:10]
            )
            top_event_ids = [row['event'] for row in top_qs]
            events_by_id = {
                e.pk: e for e in Event.objects.filter(pk__in=top_event_ids).only('pk', 'name', 'slug', 'currency')
            }

            rev_qs = (
                OrderPayment.objects.filter(
                    order__event_id__in=event_ids,
                    state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                )
                .values('order__event_id')
                .annotate(total=Sum('amount'))
            )
            event_revenue = {row['order__event_id']: row['total'] for row in rev_qs}

        orders_over_time = []
        start_date = timezone.localdate(since, timezone=tz)
        end_date = timezone.localdate(timezone=tz)
        for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
            d = d.date()
            orders_over_time.append({
                'x': d.strftime('%Y-%m-%d'),
                'ordered': ordered_by_day.get(d, 0),
                'paid': paid_by_day.get(d, 0)
            })

        label_map = dict(Order.STATUS_CHOICE)
        orders_by_status = [
            {'label': str(label_map.get(row['status'], row['status'])), 'value': row['cnt']}
            for row in status_rows
            if row['cnt'] > 0
        ]

        revenue_over_time = []
        sorted_currencies = sorted(currencies)
        cumulative = {curr: 0.0 for curr in sorted_currencies}
        for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
            d = d.date()
            day_data = {'x': d.strftime('%Y-%m-%d')}
            day_revs = rev_by_day.get(d, {})
            for curr in sorted_currencies:
                cumulative[curr] += day_revs.get(curr, 0.0)
                day_data[curr] = round(cumulative[curr], 2)
            revenue_over_time.append(day_data)

        top_events = [
            {
                'name': str(events_by_id[row['event']].name),
                'slug': events_by_id[row['event']].slug,
                'total_orders': row['total_orders'],
                'paid_orders': row['paid_orders'],
                'gross_revenue': float(event_revenue.get(row['event'], 0) or 0),
                'currency': events_by_id[row['event']].currency,
            }
            for row in top_qs
            if row['event'] in events_by_id
        ]

        return {
            'orders_over_time_json': json.dumps(orders_over_time),
            'orders_by_status_json': json.dumps(orders_by_status),
            'revenue_over_time_json': json.dumps(revenue_over_time),
            'currencies_json': json.dumps(sorted_currencies),
            'top_events': top_events,
            'has_orders': bool(status_rows),
        }

    def _get_proposals_data(self):
        event_ids = self._event_ids_for_proposals()
        if not event_ids:
            return {
                'has_proposals': False,
                'proposals_by_state_json': '[]',
                'proposals_over_time_json': '[]',
                'pending_proposal_events': [],
            }

        tz = timezone.get_current_timezone()
        since = timezone.now() - datetime.timedelta(days=60)

        with scopes_disabled():
            state_qs = list(
                Submission.objects.filter(event_id__in=event_ids)
                .values('state')
                .annotate(cnt=Count('pk'))
            )
            has_proposals = bool(state_qs)
            if not has_proposals:
                return {
                    'has_proposals': False,
                    'proposals_by_state_json': '[]',
                    'proposals_over_time_json': '[]',
                    'pending_proposal_events': [],
                }

            timeline_qs = list(
                Submission.objects.filter(
                    event_id__in=event_ids,
                    created__gte=since,
                )
                .annotate(day=TruncDate('created', tzinfo=tz))
                .values('day')
                .annotate(cnt=Count('pk'))
                .order_by('day')
            )
            by_day = {self._to_date(row['day']): row['cnt'] for row in timeline_qs}
            proposals_over_time = []
            start_date = timezone.localdate(since, timezone=tz)
            end_date = timezone.localdate(timezone=tz)
            for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
                d = d.date()
                proposals_over_time.append({'x': d.strftime('%Y-%m-%d'), 'y': by_day.get(d, 0)})

            pending_qs = list(
                Submission.objects.filter(
                    event_id__in=event_ids,
                    state=SubmissionStates.SUBMITTED,
                )
                .values('event_id')
                .annotate(pending=Count('pk'))
                .order_by('-pending')
            )
            pending_event_ids = [row['event_id'] for row in pending_qs]
            events_by_id = {
                e.pk: e for e in Event.objects.filter(pk__in=pending_event_ids).only('pk', 'name', 'slug')
            }

        label_map = dict(SubmissionStates.get_choices())
        proposals_by_state = [
            {'label': str(label_map.get(row['state'], row['state'])), 'value': row['cnt']}
            for row in state_qs
            if row['cnt'] > 0
        ]

        pending_proposal_events = [
            {
                'name': str(events_by_id[row['event_id']].name),
                'slug': events_by_id[row['event_id']].slug,
                'pending': row['pending'],
            }
            for row in pending_qs
            if row['event_id'] in events_by_id
        ]

        return {
            'has_proposals': True,
            'proposals_by_state_json': json.dumps(proposals_by_state),
            'proposals_over_time_json': json.dumps(proposals_over_time),
            'pending_proposal_events': pending_proposal_events,
        }

    def _get_checkins_data(self):
        event_ids = self._event_ids_for_checkins()
        if not event_ids:
            return {
                'show_checkins': False,
                'checkin_rate_json': '[]',
                'checkins_over_time_json': '[]',
            }

        tz = timezone.get_current_timezone()
        since = timezone.now() - datetime.timedelta(days=30)

        with scopes_disabled():
            show_checkins = CheckinList.objects.filter(event_id__in=event_ids).exists()
            if not show_checkins:
                return {
                    'show_checkins': False,
                    'checkin_rate_json': '[]',
                    'checkins_over_time_json': '[]',
                }

            event_stats = {}
            stats_qs = list(
                OrderPosition.objects.filter(
                    order__event_id__in=event_ids,
                    order__status=Order.STATUS_PAID,
                )
                .annotate(
                    checkedin=Exists(
                        Checkin.objects.filter(
                            position_id=OuterRef('pk'),
                            type=Checkin.TYPE_ENTRY,
                        )
                    )
                )
                .values('order__event_id')
                .annotate(
                    total=Count('pk'),
                    checked_in=Count('pk', filter=Q(checkedin=True))
                )
            )
            checkin_event_ids = [row['order__event_id'] for row in stats_qs]
            events_by_id = {
                e.pk: e for e in Event.objects.filter(pk__in=checkin_event_ids).only('pk', 'name')
            }
            for row in stats_qs:
                event_id = row['order__event_id']
                if event_id in events_by_id:
                    event_stats[event_id] = {
                        'event': str(events_by_id[event_id].name),
                        'total': row['total'],
                        'checked_in': row['checked_in']
                    }

            timeline_qs = list(
                Checkin.objects.filter(
                    list__event_id__in=event_ids,
                    type=Checkin.TYPE_ENTRY,
                    datetime__gte=since,
                )
                .annotate(day=TruncDate('datetime', tzinfo=tz))
                .values('day')
                .annotate(cnt=Count('pk'))
                .order_by('day')
            )

        checkin_rate = sorted(
            [stats for stats in event_stats.values() if stats['total'] > 0],
            key=lambda r: r['event']
        )

        by_day = {self._to_date(row['day']): row['cnt'] for row in timeline_qs}
        checkins_over_time = []
        start_date = timezone.localdate(since, timezone=tz)
        end_date = timezone.localdate(timezone=tz)
        for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
            d = d.date()
            checkins_over_time.append({'x': d.strftime('%Y-%m-%d'), 'y': by_day.get(d, 0)})

        has_checkins = bool(timeline_qs) or any(stats.get('checked_in', 0) > 0 for stats in event_stats.values())

        return {
            'show_checkins': has_checkins,
            'checkin_rate_json': json.dumps(checkin_rate),
            'checkins_over_time_json': json.dumps(checkins_over_time),
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        organizer = self.request.organizer
        cache = organizer.cache
        cache_key = f'organizer_analytics_{organizer.pk}_{self.request.user.pk}_{self.request.LANGUAGE_CODE}'

        data = None
        if 'refresh' not in self.request.GET:
            cached = cache.get(cache_key)
            if isinstance(cached, Mapping):
                data = cached

        if data is None:
            data = {}
            data.update(self._get_tickets_data())
            data.update(self._get_proposals_data())
            data.update(self._get_checkins_data())
            data.update(self._get_attendance_data())
            data.update(self._get_email_engagement_data())
            data.update(self._get_follower_growth_data())
            cache.set(cache_key, data, 600)

        attendance_daily_by_event = data.get('attendance_daily_by_event', {})
        attendance_presentation = self._project_attendance(
            attendance_daily_by_event=attendance_daily_by_event,
            attendance_events=data.get('attendance_events') or [],
            date_labels=self._attendance_date_labels(
                timezone.now(),
                timezone.get_current_timezone(),
            ),
            requested_event=self.request.GET.get('attendance_event'),
        )

        ctx.update(data)
        ctx.update(attendance_presentation)

        # Client-side filters: keep full top-events list and attendance payload in the page.
        top_events = list(data.get('top_events') or [])
        currencies = sorted({event.get('currency') for event in top_events if event.get('currency')})
        selected_currency = (self.request.GET.get('revenue_currency') or '').strip().upper()
        if selected_currency and selected_currency not in currencies:
            selected_currency = ''

        date_labels = self._attendance_date_labels(
            timezone.now(),
            timezone.get_current_timezone(),
        )
        daily_by_event = data.get('attendance_daily_by_event') or {}
        # JSON object keys must be strings
        daily_payload = {str(event_id): days for event_id, days in daily_by_event.items()}

        ctx['top_events'] = top_events
        ctx['top_event_currencies'] = currencies if len(currencies) > 1 else []
        ctx['selected_revenue_currency'] = selected_currency
        ctx['attendance_daily_by_event_client'] = daily_payload
        ctx['attendance_date_labels'] = list(date_labels)
        return ctx
