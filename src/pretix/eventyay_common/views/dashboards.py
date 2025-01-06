import pytz
from django.conf import settings
from django.db.models import (
    Count, Exists, IntegerField, Max, Min, OuterRef, Q, Subquery,
)
from django.db.models.functions import Coalesce, Greatest
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import escape
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _, pgettext

from pretix.base.models import Order, RequiredAction
from pretix.control.signals import user_dashboard_widgets
from pretix.helpers.daterange import daterange
from pretix.helpers.plugin_enable import is_video_enabled

from .event import EventCreatedFor


def organiser_dashboard(request):
    widgets = []
    for r, result in user_dashboard_widgets.send(request, user=request.user):
        widgets.extend(result)

    ctx = {
        'widgets': rearrange(widgets),
        'can_create_event': request.user.teams.filter(
            can_create_events=True
        ).exists(),
        'upcoming': widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True)
            .filter(
                Q(has_subevents=False)
                & Q(
                    Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                    | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
                )
            ).order_by('date_from', 'order_to', 'pk'),
            request.user,
            7,
            lazy=True,
        ),
        'past': widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True)
            .filter(
                Q(has_subevents=False)
                & Q(
                    Q(Q(date_to__isnull=True) & Q(date_from__lt=now()))
                    | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
                )
            ).order_by('-order_to', 'pk'),
            request.user,
            8,
            lazy=True,
        ),
        'series': widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True).filter(
                has_subevents=True
            ).order_by('-order_to', 'pk'),
            request.user,
            8,
            lazy=True
        )
    }

    return render(request, 'eventyay_common/dashboard/dashboard.html', ctx)


def rearrange(widgets: list):
    """
    Sort widget boxes according to priority.
    """
    mapping = {
        'small': 1,
        'big': 2,
        'full': 3,
    }

    def sort_key(element):
        return (
            element.get('priority', 1),
            mapping.get(element.get('display_size', 'small'), 1),
        )

    return sorted(widgets, key=sort_key, reverse=True)


def widgets_for_event_qs(request, qs, user, nmax, lazy=False):
    widgets = []

    tpl = """
        <a href="{url}" class="event">
            <div class="name">{event}</div>
            <div class="daterange">{daterange}</div>
            <div class="times">{times}</div>
        </a>
        <div class="bottomrow">
            <a href="{ticket_url}" class="component">
                Ticket
            </a>
            {talk_button}
            {video_button}
        </div>
    """

    if lazy:
        events = qs[:nmax]
    else:
        events = qs.prefetch_related(
            '_settings_objects', 'organizer___settings_objects'
        ).select_related('organizer')[:nmax]

    for event in events:
        dr = None

        if not lazy:
            tzname = event.cache.get_or_set('timezone', lambda e=event: e.settings.timezone)
            tz = pytz.timezone(tzname)
            if event.has_subevents:
                dr = (
                    pgettext("subevent", "No dates")
                    if event.min_from is None
                    else daterange(
                        (event.min_from).astimezone(tz),
                        (event.max_fromto or event.max_to or event.max_from).astimezone(tz),
                    )
                )
            elif event.date_to:
                dr = daterange(event.date_from.astimezone(tz), event.date_to.astimezone(tz))
            else:
                dr = date_format(event.date_from.astimezone(tz), "DATE_FORMAT")

        if is_video_enabled(event):
            url = reverse(
                'eventyay_common:event.create_access_to_video',
                kwargs={
                    'event': event.slug,
                    'organizer': event.organizer.slug
                }
            )
            video_button = f"""
            <a href={url}" class="component">{_('Video')}</a>
            """
        else:
            video_button = f"""
                <a href="#" data-toggle="modal" data-target="#alert-modal" class="component">
                    {_('Video')}
                </a>
            """
        if (
            event.settings.create_for == EventCreatedFor.BOTH.value
            or event.settings.talk_schedule_public is not None
        ):
            talk_button = f"""<a href="{event.talk_dashboard_url}" class="middle-component">{_('Talk')}</a>"""
        else:
            talk_button = f"""
                <a href="#" data-toggle="modal" data-target="#alert-modal" class="middle-component">
                    {_('Talk')}
                </a>
            """

        widgets.append({
            'content': (
                ''
                if lazy
                else tpl.format(
                    event=escape(event.name),
                    times=(
                        _('Event series')
                        if event.has_subevents
                        else (
                            (
                                date_format(
                                    event.date_admission.astimezone(tz),
                                    'TIME_FORMAT',
                                ) + ' / '
                            )
                            if event.date_admission and event.date_admission != event.date_from
                            else ''
                        )
                        + (
                            date_format(event.date_from.astimezone(tz), 'TIME_FORMAT')
                            if event.date_from
                            else ''
                        )
                    ) + (
                        f' <span class="fa fa-globe text-muted" data-toggle="tooltip" title="{tzname}"></span>'
                        if tzname != request.timezone and not event.has_subevents
                        else ''
                    ),
                    url=reverse(
                        "eventyay_common:event.update",
                        kwargs={
                            "organizer": event.organizer.slug,
                            "event": event.slug,
                        }
                    ),
                    daterange=dr,
                    ticket_url=reverse(
                        'control:event.index',
                        kwargs={
                            'event': event.slug,
                            'organizer': event.organizer.slug
                        }
                    ),
                    video_button=video_button,
                    talk_button=talk_button
                )
            ),
            'display_size': 'small',
            'lazy': f'event-{event.pk}',
            'priority': 100,
            'container_class': 'widget-container widget-container-event',
        })
    return widgets


def annotated_event_query(request, lazy=False):
    active_orders = Order.objects.filter(
        event=OuterRef('pk'),
        status__in=[Order.STATUS_PENDING, Order.STATUS_PAID]
    ).order_by().values('event').annotate(
        c=Count('*')
    ).values(
        'c'
    )

    required_actions = RequiredAction.objects.filter(
        event=OuterRef('pk'),
        done=False
    )
    qs = request.user.get_events_with_any_permission(request)
    if not lazy:
        qs = qs.annotate(
            order_count=Subquery(active_orders, output_field=IntegerField()),
            has_ra=Exists(required_actions)
        )
    qs = qs.annotate(
        min_from=Min('subevents__date_from'),
        max_from=Max('subevents__date_from'),
        max_to=Max('subevents__date_to'),
        max_fromto=Greatest(Max('subevents__date_to'), Max('subevents__date_from')),
    ).annotate(
        order_to=Coalesce('max_fromto', 'max_to', 'max_from', 'date_to', 'date_from'),
    )
    return qs


def user_index_widgets_lazy(request):
    widgets = []
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request).filter(
            Q(has_subevents=False) &
            Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
            )
        ).order_by('date_from', 'order_to', 'pk'),
        request.user,
        7
    )
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request).filter(
            Q(has_subevents=False) &
            Q(
                Q(Q(date_to__isnull=True) & Q(date_from__lt=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
            )
        ).order_by('-order_to', 'pk'),
        request.user,
        8
    )
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request).filter(
            has_subevents=True
        ).order_by('-order_to', 'pk'),
        request.user,
        8
    )
    return JsonResponse({'widgets': widgets})
