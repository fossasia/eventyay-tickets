"""Helpers for the common user dashboard (onboarding + organised events)."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope, scopes_disabled

from eventyay.base.meetup import is_meetup_event
from eventyay.base.models import Event, Order, Submission, User
from eventyay.base.settings import is_event_series_creation_enabled, is_meetup_creation_enabled
from eventyay.eventyay_common.permissions import (
    user_has_talk_dashboard_access,
    user_has_ticket_dashboard_access,
    user_has_video_dashboard_access,
)
from eventyay.eventyay_common.utils import EventCreatedFor
from eventyay.helpers.daterange import daterange
from eventyay.multidomain.urlreverse import eventreverse

RECOMMENDED_EVENTS_LIMIT = 6
MANAGED_EVENTS_LIMIT = 8

TICKET_PERMISSION_DIALOG_ID = 'ticket-permission-dialog'
TALK_PERMISSION_DIALOG_ID = 'talk-permission-dialog'
VIDEO_PERMISSION_DIALOG_ID = 'video-permission-dialog'


def user_has_orders(user: User) -> bool:
    if not user.email:
        return False
    with scopes_disabled():
        return Order.objects.filter(email__iexact=user.email).exists()


def user_has_sessions_or_proposals(user: User) -> bool:
    if not user.email:
        return False
    with scopes_disabled():
        return Submission.objects.filter(speakers__email__iexact=user.email).exists()


def user_has_organised_events(user: User, request: HttpRequest | None = None) -> bool:
    with scopes_disabled():
        return user.get_events_with_any_permission(request).exists()


def user_needs_onboarding(user: User, request: HttpRequest | None = None) -> bool:
    """Return True when the user has no personal Eventyay activity yet."""
    if user_has_orders(user):
        return False
    if user_has_sessions_or_proposals(user):
        return False
    if user_has_organised_events(user, request):
        return False
    return True


def get_missing_profile_fields(user: User) -> list[str]:
    """Return human-readable account fields that are still missing."""
    missing: list[str] = []
    if not (user.fullname or '').strip():
        missing.append(str(_('full name')))
    if not user.has_profile_picture:
        missing.append(str(_('profile picture')))
    return missing


def format_profile_incomplete_message(missing: list[str]) -> str:
    """Build a short prompt that names only the missing profile fields."""
    if not missing:
        return ''
    if len(missing) == 1:
        return str(_('Add your %(item)s to finish your profile.') % {'item': missing[0]})
    if len(missing) == 2:
        return str(
            _('Add your %(first)s and %(second)s to finish your profile.')
            % {'first': missing[0], 'second': missing[1]}
        )
    *head, last = missing
    return str(
        _('Add your %(items)s, and %(last)s to finish your profile.')
        % {'items': ', '.join(head), 'last': last}
    )


def is_profile_incomplete(user: User) -> bool:
    """Account profile is incomplete without a display name or photo."""
    return bool(get_missing_profile_fields(user))


def build_profile_prompt_context(user: User) -> dict[str, Any]:
    missing = get_missing_profile_fields(user)
    return {
        'profile_incomplete': bool(missing),
        'profile_incomplete_message': format_profile_incomplete_message(missing),
        'edit_profile_url': reverse('eventyay_common:account.general'),
    }


def _public_upcoming_events_qs():
    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        Event.objects.select_related('organizer')
        .prefetch_related('_settings_objects', 'cfp')
        .filter(live=True, is_public=True, testmode=False)
        .filter(Q(startpage_visible=True) | Q(startpage_featured=True))
        .filter(Q(date_to__gte=today) | Q(date_to__isnull=True, date_from__gte=today))
        .exclude(_settings_objects__key='talks_testmode', _settings_objects__value='True')
        .order_by('-startpage_featured', 'date_from')
    )


def _event_date_range(event: Event) -> str:
    tzname = event.settings.get('timezone') or event.timezone or 'UTC'
    tz = ZoneInfo(str(tzname))
    if event.has_subevents:
        return str(_('Event series'))
    if event.date_to:
        return daterange(event.date_from.astimezone(tz), event.date_to.astimezone(tz))
    return event.get_date_range_display()


def _event_time_label(event: Event) -> str:
    if event.has_subevents:
        return str(_('Event series'))
    tzname = event.settings.get('timezone') or event.timezone or 'UTC'
    tz = ZoneInfo(str(tzname))
    if not event.date_from:
        return ''
    return date_format(event.date_from.astimezone(tz), 'TIME_FORMAT')


def _event_location_label(event: Event) -> str:
    location = str(event.location or '').strip()
    if location:
        return location.splitlines()[0]
    tzname = event.settings.get('timezone') or event.timezone
    if tzname:
        return str(tzname)
    return ''


def _event_cfp_is_open(event: Event) -> bool:
    from eventyay.base.models.cfp import CfP

    try:
        with scope(event=event):
            cfp = event.cfp
            return bool(cfp.is_open)
    except CfP.DoesNotExist:
        return False


def _event_kind(event: Event) -> dict[str, str]:
    """Return a short type label for cards: event, series, or meetup."""
    if is_meetup_event(event):
        return {
            'kind': 'meetup',
            'label': str(_('Meetup')),
            'tone': 'success',
            'icon': 'users',
        }
    if event.has_subevents:
        return {
            'kind': 'series',
            'label': str(_('Series')),
            'tone': 'warning',
            'icon': 'calendar',
        }
    return {
        'kind': 'event',
        'label': str(_('Event')),
        'tone': 'primary',
        'icon': 'ticket',
    }


def _event_badges(event: Event) -> list[dict[str, str]]:
    badges: list[dict[str, str]] = []
    if event.presale_is_running:
        badges.append({'label': str(_('Tickets on sale')), 'tone': 'success'})
    if _event_cfp_is_open(event):
        badges.append({'label': str(_('Call for proposals')), 'tone': 'accent'})
    return badges


def _event_primary_action(event: Event) -> dict[str, str]:
    url = eventreverse(event, 'presale:event.index')
    cfp_open = _event_cfp_is_open(event)
    if cfp_open and not event.presale_is_running:
        return {'label': str(_('Submit proposal')), 'url': url}
    if event.presale_is_running:
        return {'label': str(_('Register')), 'url': url}
    return {'label': str(_('View event')), 'url': url}


def _base_event_card(event: Event) -> dict[str, Any]:
    return {
        'name': str(event.name),
        'image_url': event.preview_image_url_with_fallback or '',
        'date_range': _event_date_range(event),
        'time_label': _event_time_label(event),
        'location': _event_location_label(event),
        'kind': _event_kind(event),
        'badges': _event_badges(event),
        'organizer_name': str(event.organizer.name) if event.organizer_id else '',
    }


def build_recommended_event_cards(limit: int = RECOMMENDED_EVENTS_LIMIT) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    with scopes_disabled():
        events = list(_public_upcoming_events_qs()[:limit])
    for event in events:
        if event.has_component_testmode:
            continue
        with scope(event=event):
            card = _base_event_card(event)
            card['url'] = eventreverse(event, 'presale:event.index')
            card['primary_action'] = _event_primary_action(event)
            cards.append(card)
    return cards


def _module_action(
    *,
    label: str,
    icon: str,
    tone: str,
    url: str | None = None,
    dialog_id: str | None = None,
    modal_target: str | None = None,
) -> dict[str, Any]:
    return {
        'label': label,
        'icon': icon,
        'tone': tone,
        'url': url or '#',
        'dialog_id': dialog_id,
        'modal_target': modal_target,
    }


def _ticket_module_action(event: Event, request: HttpRequest) -> dict[str, Any]:
    if user_has_ticket_dashboard_access(request.user, event.organizer, event, request=request):
        return _module_action(
            label=str(_('Tickets')),
            icon='ticket',
            tone='tickets',
            url=reverse(
                'control:event.index',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            ),
        )
    return _module_action(
        label=str(_('Tickets')),
        icon='ticket',
        tone='tickets',
        dialog_id=TICKET_PERMISSION_DIALOG_ID,
    )


def _talk_module_action(event: Event, request: HttpRequest) -> dict[str, Any]:
    if event.settings.create_for != EventCreatedFor.BOTH.value and event.settings.talk_schedule_public is None:
        return _module_action(
            label=str(_('Talks')),
            icon='microphone',
            tone='talks',
            modal_target='#alert-modal',
        )
    if not user_has_talk_dashboard_access(request.user, event.organizer, event, request=request):
        return _module_action(
            label=str(_('Talks')),
            icon='microphone',
            tone='talks',
            dialog_id=TALK_PERMISSION_DIALOG_ID,
        )
    return _module_action(
        label=str(_('Talks')),
        icon='microphone',
        tone='talks',
        url=reverse('orga:event.dashboard', kwargs={'organizer': event.organizer.slug, 'event': event.slug}),
    )


def _video_module_action(event: Event, request: HttpRequest) -> dict[str, Any]:
    if user_has_video_dashboard_access(request.user, event.organizer, event, request=request):
        return _module_action(
            label=str(_('Video')),
            icon='video-camera',
            tone='video',
            url=reverse(
                'eventyay_common:event.create_access_to_video',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            ),
        )
    return _module_action(
        label=str(_('Video')),
        icon='video-camera',
        tone='video',
        dialog_id=VIDEO_PERMISSION_DIALOG_ID,
    )


def build_managed_event_card(event: Event, request: HttpRequest) -> dict[str, Any]:
    with scope(event=event):
        card = _base_event_card(event)
        card['url'] = reverse(
            'eventyay_common:event.index',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )
        card['module_actions'] = [
            _ticket_module_action(event, request),
            _talk_module_action(event, request),
            _video_module_action(event, request),
        ]
    return card


def build_managed_event_cards(
    request: HttpRequest, qs: QuerySet[Event], limit: int = MANAGED_EVENTS_LIMIT
) -> list[dict[str, Any]]:
    events = list(qs.prefetch_related('_settings_objects', 'cfp').select_related('organizer')[:limit])
    return [build_managed_event_card(event, request) for event in events]


def build_create_actions(request: HttpRequest) -> list[dict[str, Any]]:
    if not request.user.teams.filter(can_create_events=True).exists():
        return []
    actions = [
        {
            'title': str(_('Create event')),
            'description': str(_('Set up tickets, talks, and video for a new event.')),
            'url': reverse('eventyay_common:events.add'),
            'icon': 'plus-circle',
            'tone': 'primary',
        }
    ]
    if is_event_series_creation_enabled(request):
        actions.append(
            {
                'title': str(_('Create event series')),
                'description': str(_('Launch a multi-date series with shared settings.')),
                'url': reverse('eventyay_common:events.add') + '?series=1',
                'icon': 'calendar',
                'tone': 'accent',
            }
        )
    if is_meetup_creation_enabled(request):
        actions.append(
            {
                'title': str(_('Create meetup')),
                'description': str(_('Start a lightweight meetup with a simpler setup.')),
                'url': reverse('eventyay_common:events.add') + '?meetup=1',
                'icon': 'users',
                'tone': 'success',
            }
        )
    return actions


def build_onboarding_context(request: HttpRequest) -> dict[str, Any]:
    user = request.user
    can_create_event = user.teams.filter(can_create_events=True).exists()
    return {
        'is_onboarding_dashboard': True,
        'can_create_event': can_create_event,
        **build_profile_prompt_context(user),
        'recommended_events': build_recommended_event_cards(),
        'browse_events_url': reverse('presale:index'),
        'upcoming_events_url': reverse('presale:events.upcoming'),
        'open_calls_url': reverse('presale:events.upcoming') + '?cfp=open',
        'create_event_url': reverse('eventyay_common:events.add'),
        'search_events_url': reverse('presale:index'),
    }


def build_organiser_dashboard_context(request: HttpRequest, annotated_qs_factory) -> dict[str, Any]:
    """Build context for the organised-events dashboard.

    ``annotated_qs_factory`` is ``annotated_event_query`` from dashboards.py to
    avoid a circular import.
    """
    upcoming_qs = (
        annotated_qs_factory(request, lazy=False)
        .filter(
            Q(has_subevents=False)
            & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
            )
        )
        .order_by('date_from', 'order_to', 'pk')
    )
    past_qs = (
        annotated_qs_factory(request, lazy=False)
        .filter(
            Q(has_subevents=False)
            & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__lt=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
            )
        )
        .order_by('-order_to', 'pk')
    )
    series_qs = annotated_qs_factory(request, lazy=False).filter(has_subevents=True).order_by('-order_to', 'pk')

    can_create_event = request.user.teams.filter(can_create_events=True).exists()
    return {
        'is_onboarding_dashboard': False,
        'can_create_event': can_create_event,
        'create_actions': build_create_actions(request),
        'upcoming_events': build_managed_event_cards(request, upcoming_qs, limit=7),
        'past_events': build_managed_event_cards(request, past_qs, limit=8),
        'series_events': build_managed_event_cards(request, series_qs, limit=8),
        'events_list_url': reverse('eventyay_common:events'),
        'upcoming_list_url': reverse('eventyay_common:events') + '?ordering=date_from&status=date_future',
        'past_list_url': reverse('eventyay_common:events') + '?ordering=date_from&status=-date_to',
        'series_list_url': reverse('eventyay_common:events') + '?ordering=-date_to&status=series',
        **build_profile_prompt_context(request.user),
        'browse_events_url': reverse('presale:index'),
    }
