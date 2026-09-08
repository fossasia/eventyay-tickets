"""Overview context for the organizer dashboard (onboarding + data-rich)."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.timesince import timesince
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Device,
    Event,
    LogEntry,
    Order,
    OrderPayment,
    QueuedMail,
    Submission,
    SubmissionStates,
    Team,
)
from eventyay.eventyay_common.navigation import get_organizer_navigation
from eventyay.multidomain.urlreverse import build_absolute_uri


def _is_hubspot_nav_item(item: dict) -> bool:
    url = item.get('url', '')
    label = str(item.get('label', '')).lower()
    return 'hubspot' in url or label == 'hubspot'


def _is_social_media_nav_item(item: dict) -> bool:
    url = item.get('url', '')
    label = str(item.get('label', '')).lower()
    return 'socialmedia' in url or 'social_media' in url or 'social-media' in url or label == 'social media accounts'


def _event_status(event: Event, now) -> dict[str, str]:
    end = event.date_to or event.date_from
    if not event.live:
        return {'label': _('Draft'), 'class': 'draft'}
    if end and end < now:
        return {'label': _('Past'), 'class': 'past'}
    if event.date_from and event.date_from > now:
        return {'label': _('Upcoming'), 'class': 'upcoming'}
    return {'label': _('Live'), 'class': 'live'}


def _plugin_tool_urls(request) -> tuple[str | None, str | None]:
    hubspot_url = None
    social_url = None
    try:
        nav = get_organizer_navigation(request)
    except (AttributeError, TypeError, ValueError):
        return None, None
    for item in nav:
        for child in item.get('children') or []:
            if hubspot_url is None and _is_hubspot_nav_item(child):
                hubspot_url = child.get('url')
            if social_url is None and _is_social_media_nav_item(child):
                social_url = child.get('url')
        if hubspot_url is None and _is_hubspot_nav_item(item):
            hubspot_url = item.get('url')
        if social_url is None and _is_social_media_nav_item(item):
            social_url = item.get('url')
    return hubspot_url, social_url


def build_organizer_dashboard_overview(request, analytics: Mapping[str, Any]) -> dict[str, Any]:
    """Build KPI, portfolio, tools, activity, and mode flags for the organizer dashboard."""
    organizer = request.organizer
    orgapermset = getattr(request, 'orgapermset', set()) or set()
    now = timezone.now()
    slug = organizer.slug

    events_qs = (
        request.user.get_events_with_any_permission(request)
        .filter(organizer=organizer)
        .order_by('-date_from')
    )
    all_event_ids = list(events_qs.values_list('pk', flat=True))

    with scopes_disabled():
        full_events = list(
            Event.objects.filter(pk__in=all_event_ids).only(
                'pk', 'name', 'slug', 'live', 'date_from', 'date_to', 'currency'
            )
        )
        live_count = 0
        draft_count = 0
        upcoming_count = 0
        for e in full_events:
            if not e.live:
                draft_count += 1
                continue
            end = e.date_to or e.date_from
            if end and end < now:
                continue
            if e.date_from and e.date_from > now:
                upcoming_count += 1
            else:
                live_count += 1

        order_event_ids = list(
            request.user.get_events_with_permission('can_view_orders', request=request)
            .filter(organizer=organizer)
            .values_list('pk', flat=True)
        )
        proposal_event_ids = list(
            request.user.get_events_with_permission('can_change_submissions', request=request)
            .filter(organizer=organizer)
            .values_list('pk', flat=True)
        )

        paid_orders = 0
        gross_revenue = Decimal('0')
        revenue_by_currency = []
        pending_approval_orders = 0
        if order_event_ids:
            paid_orders = Order.objects.filter(
                event_id__in=order_event_ids, status=Order.STATUS_PAID
            ).count()
            revenue_by_currency = list(
                OrderPayment.objects.filter(
                    order__event_id__in=order_event_ids,
                    state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                )
                .values('order__event__currency')
                .annotate(total=Sum('amount'))
                .order_by('-total')
            )
            pending_approval_orders = Order.objects.filter(
                event_id__in=order_event_ids,
                status=Order.STATUS_PENDING,
                require_approval=True,
            ).count()

        confirmed_sessions = 0
        if proposal_event_ids:
            confirmed_sessions = Submission.objects.filter(
                event_id__in=proposal_event_ids,
                state=SubmissionStates.CONFIRMED,
            ).count()

        emails_sent = 0
        emails_queued = 0
        if proposal_event_ids:
            mail_agg = QueuedMail.objects.filter(event_id__in=proposal_event_ids).aggregate(
                sent_count=Count('pk', filter=Q(sent__isnull=False)),
                queued_count=Count('pk', filter=Q(sent__isnull=True)),
            )
            emails_sent = mail_agg['sent_count'] or 0
            emails_queued = mail_agg['queued_count'] or 0

        # Per-event portfolio stats for first N events (prioritize live, upcoming, recent)
        portfolio_candidates = sorted(
            full_events,
            key=lambda e: (
                0 if (e.live and e.date_from and e.date_from <= now and (not e.date_to or e.date_to >= now)) else 1,
                0 if (e.live and e.date_from and e.date_from > now) else 1,
                0 if not e.live else 1,
                -(e.date_from.timestamp() if e.date_from else 0),
            ),
        )[:8]
        portfolio_ids = [e.pk for e in portfolio_candidates]

        orders_by_event = {}
        revenue_by_event = {}
        sessions_by_event = {}
        order_event_id_set = set(order_event_ids)
        proposal_event_id_set = set(proposal_event_ids)
        portfolio_order_ids = [pk for pk in portfolio_ids if pk in order_event_id_set]
        portfolio_proposal_ids = [pk for pk in portfolio_ids if pk in proposal_event_id_set]
        if portfolio_order_ids:
            for row in (
                Order.objects.filter(event_id__in=portfolio_order_ids)
                .values('event_id')
                .annotate(total=Count('pk'))
            ):
                orders_by_event[row['event_id']] = row['total']
            for row in (
                OrderPayment.objects.filter(
                    order__event_id__in=portfolio_order_ids,
                    state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                )
                .values('order__event_id')
                .annotate(total=Sum('amount'))
            ):
                revenue_by_event[row['order__event_id']] = row['total'] or Decimal('0')
        if portfolio_proposal_ids:
            for row in (
                Submission.objects.filter(
                    event_id__in=portfolio_proposal_ids,
                    state=SubmissionStates.CONFIRMED,
                )
                .values('event_id')
                .annotate(total=Count('pk'))
            ):
                sessions_by_event[row['event_id']] = row['total']

        team_member_count = (
            Team.objects.filter(organizer=organizer)
            .aggregate(n=Count('members', distinct=True))['n']
            or 0
        )
        device_count = Device.objects.filter(organizer=organizer).count()

        org_ct = organizer.logs_content_type
        activity_q = Q(content_type=org_ct, object_id=organizer.pk)
        if all_event_ids:
            activity_q |= Q(event_id__in=all_event_ids)
        activity_entries = list(
            LogEntry.objects.filter(activity_q)
            .select_related('user', 'event')
            .order_by('-datetime', '-id')[:8]
        )

    currency = full_events[0].currency if full_events else (getattr(organizer, 'default_currency', None) or 'USD')
    gross_revenue_is_money = True
    if revenue_by_currency:
        # Never sum amounts across currencies; show the largest single-currency total.
        top_revenue = revenue_by_currency[0]
        currency = top_revenue['order__event__currency'] or currency
        gross_revenue = top_revenue['total'] or Decimal('0')
        if len(revenue_by_currency) > 1:
            # Multiple currencies: render a plain multi-currency summary instead of a mixed total.
            gross_revenue_is_money = False
            gross_revenue = ' · '.join(
                f"{row['order__event__currency']} {row['total'] or Decimal('0')}"
                for row in revenue_by_currency
                if row.get('order__event__currency')
            )

    events_url = reverse('eventyay_common:organizer.events', kwargs={'organizer': slug})
    create_event_url = reverse('eventyay_common:events.add') + f'?organizer={slug}'
    settings_url = reverse('eventyay_common:organizer.edit', kwargs={'organizer': slug})
    teams_url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': slug}) + '?section=permissions'
    devices_url = reverse('eventyay_common:organizer.devices', kwargs={'organizer': slug})
    public_profile_url = build_absolute_uri(organizer, 'presale:organizer.index')

    hubspot_url, social_url = _plugin_tool_urls(request)

    can_create = 'can_create_events' in orgapermset
    can_settings = 'can_change_organizer_settings' in orgapermset
    can_teams = 'can_change_teams' in orgapermset

    kpi_cards = [
        {
            'label': _('Live events'),
            'value': live_count,
            'icon': 'rss',
            'tone': 'green',
            'url': events_url,
        },
        {
            'label': _('Draft events'),
            'value': draft_count,
            'icon': 'file-text-o',
            'tone': 'blue',
            'url': events_url,
        },
        {
            'label': _('Upcoming events'),
            'value': upcoming_count,
            'icon': 'calendar',
            'tone': 'purple',
            'url': events_url,
        },
        {
            'label': _('Paid orders'),
            'value': paid_orders,
            'icon': 'shopping-cart',
            'tone': 'orange',
            'url': events_url,
        },
        {
            'label': _('Gross revenue'),
            'value': gross_revenue,
            'value_is_money': gross_revenue_is_money,
            'currency': currency,
            'icon': 'money',
            'tone': 'green',
            'url': events_url,
        },
        {
            'label': _('Confirmed sessions'),
            'value': confirmed_sessions,
            'icon': 'microphone',
            'tone': 'blue',
            'url': events_url,
        },
        {
            'label': _('Emails sent'),
            'value': emails_sent,
            'icon': 'envelope',
            'tone': 'purple',
            'url': events_url,
        },
        {
            'label': _('Emails queued'),
            'value': emails_queued,
            'icon': 'clock-o',
            'tone': 'muted',
            'url': events_url,
        },
    ]

    portfolio_events = []
    for e in portfolio_candidates:
        status = _event_status(e, now)
        portfolio_events.append(
            {
                'name': str(e.name),
                'slug': e.slug,
                'status_label': status['label'],
                'status_class': status['class'],
                'start_date': date_format(e.date_from, 'DATE_FORMAT') if e.date_from else '—',
                'orders': orders_by_event.get(e.pk, 0),
                'revenue': revenue_by_event.get(e.pk, Decimal('0')),
                'currency': e.currency,
                'sessions': sessions_by_event.get(e.pk, 0),
                'dashboard_url': reverse(
                    'eventyay_common:event.index',
                    kwargs={'organizer': slug, 'event': e.slug},
                ),
                'is_draft': not e.live,
            }
        )

    has_published = any(e['status_class'] != 'draft' for e in portfolio_events)
    total_events = len(full_events)

    has_meaningful_data = bool(
        live_count
        or upcoming_count
        or paid_orders
        or confirmed_sessions
        or analytics.get('has_orders')
        or analytics.get('has_proposals')
    )
    is_onboarding = not has_meaningful_data

    getting_started = []
    if is_onboarding:
        if can_create:
            getting_started.append(
                {
                    'title': _('Create your first event'),
                    'description': _('Set up tickets, talks, and video under this organizer.'),
                    'icon': 'calendar-plus-o',
                    'tone': 'blue',
                    'url': create_event_url,
                    'cta': _('Create event'),
                }
            )
        if can_settings:
            getting_started.append(
                {
                    'title': _('Complete organizer settings'),
                    'description': _('Add branding, contact details, and public profile information.'),
                    'icon': 'cog',
                    'tone': 'purple',
                    'url': settings_url,
                    'cta': _('Open settings'),
                }
            )
        if can_teams:
            getting_started.append(
                {
                    'title': _('Invite your team'),
                    'description': _('Give colleagues access to events, tickets, and talks.'),
                    'icon': 'user-plus',
                    'tone': 'green',
                    'url': teams_url,
                    'cta': _('Manage teams'),
                }
            )
        if can_settings:
            getting_started.append(
                {
                    'title': _('Connect integrations'),
                    'description': _('Link HubSpot, social accounts, and check-in devices when ready.'),
                    'icon': 'puzzle-piece',
                    'tone': 'orange',
                    'url': hubspot_url or settings_url,
                    'cta': _('Explore tools'),
                }
            )

    action_required = []
    if not is_onboarding:
        if draft_count:
            action_required.append(
                {
                    'title': ngettext(
                        '%(count)d draft event incomplete',
                        '%(count)d draft events incomplete',
                        draft_count,
                    )
                    % {'count': draft_count},
                    'description': _('Finish setup and publish when you are ready.'),
                    'icon': 'file-text-o',
                    'tone': 'caution',
                    'url': events_url,
                    'cta': _('Review drafts'),
                }
            )
        if pending_approval_orders:
            action_required.append(
                {
                    'title': ngettext(
                        '%(count)d order needs approval',
                        '%(count)d orders need approval',
                        pending_approval_orders,
                    )
                    % {'count': pending_approval_orders},
                    'description': _('Review pending ticket orders across your events.'),
                    'icon': 'shopping-cart',
                    'tone': 'warning',
                    'url': events_url,
                    'cta': _('Review orders'),
                }
            )
        integrations_attention = 0
        if can_settings and not hubspot_url:
            integrations_attention += 0  # plugin may simply be unavailable
        if device_count == 0 and can_settings:
            integrations_attention += 1
        if team_member_count <= 1 and can_teams:
            integrations_attention += 1
        if integrations_attention:
            action_required.append(
                {
                    'title': ngettext(
                        '%(count)d integration needs attention',
                        '%(count)d integrations need attention',
                        integrations_attention,
                    )
                    % {'count': integrations_attention},
                    'description': _('Connect devices, invite teammates, or finish setup.'),
                    'icon': 'puzzle-piece',
                    'tone': 'info',
                    'url': settings_url,
                    'cta': _('Manage integrations'),
                }
            )

    organizer_tools = [
        {
            'title': _('HubSpot'),
            'description': _('Sync contacts and CRM data with your events.'),
            'icon': 'exchange',
            'badge': _('Connected') if hubspot_url else _('Not connected'),
            'badge_tone': 'success' if hubspot_url else 'muted',
            'url': hubspot_url or settings_url,
            'cta': _('Manage integration') if hubspot_url else _('Set up HubSpot'),
            'available': can_settings,
        },
        {
            'title': _('Social Media'),
            'description': _('Connect accounts used for event promotion.'),
            'icon': 'share-alt',
            'badge': _('Connected') if social_url else _('Not connected'),
            'badge_tone': 'success' if social_url else 'muted',
            'url': social_url or settings_url,
            'cta': _('Manage accounts') if social_url else _('Connect accounts'),
            'available': can_settings,
        },
        {
            'title': _('Devices'),
            'description': _('Register check-in devices for your events.'),
            'icon': 'tablet',
            'badge': (
                ngettext('%(count)d registered', '%(count)d registered', device_count) % {'count': device_count}
                if device_count
                else _('No devices')
            ),
            'badge_tone': 'info' if device_count else 'muted',
            'url': devices_url,
            'cta': _('Manage devices'),
            'available': can_settings,
        },
        {
            'title': _('Teams'),
            'description': _('Manage who can access this organizer account.'),
            'icon': 'users',
            'badge': (
                ngettext('%(count)d member', '%(count)d members', team_member_count) % {'count': team_member_count}
                if team_member_count
                else _('No members')
            ),
            'badge_tone': 'info' if team_member_count else 'muted',
            'url': teams_url,
            'cta': _('Manage teams'),
            'available': can_teams,
        },
    ]

    recent_activity = []
    for entry in activity_entries:
        display = entry.action_type
        try:
            rendered = entry.display()
            if rendered:
                display = rendered
        except (TypeError, ValueError, AttributeError):
            pass
        recent_activity.append(
            {
                'title': display,
                'detail': str(entry.event.name) if entry.event_id else str(organizer.name),
                'when': timesince(entry.datetime),
                'icon': 'bolt' if entry.event_id else 'building',
                'tone': 'blue' if entry.event_id else 'green',
            }
        )

    subtitle = (
        _('Get started with your organizer account.')
        if is_onboarding
        else _('Overview across all events under this organizer.')
    )

    return {
        'is_onboarding': is_onboarding,
        'dashboard_subtitle': subtitle,
        'kpi_cards': kpi_cards,
        'getting_started': getting_started,
        'action_required': action_required,
        'portfolio_events': portfolio_events,
        'portfolio_has_published': has_published,
        'total_events': total_events,
        'organizer_tools': [t for t in organizer_tools if t.get('available')],
        'recent_activity': recent_activity,
        'public_profile_url': public_profile_url,
        'create_event_url': create_event_url,
        'events_list_url': events_url,
        'organizer_settings_url': settings_url,
        'can_create_event': can_create,
        'can_change_organizer_settings': can_settings,
        'live_events_count': live_count,
        'draft_events_count': draft_count,
    }
