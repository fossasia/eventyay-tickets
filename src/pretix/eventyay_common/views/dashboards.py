from typing import Any, Dict, List, Tuple

import pytz
from django.db.models import (
    Count, Exists, IntegerField, Max, Min, OuterRef, Q, QuerySet, Subquery,
)
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import escape
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from pytz.tzinfo import DstTzInfo

from pretix.base.models import Event, Order, RequiredAction
from pretix.control.signals import user_dashboard_widgets
from pretix.helpers.daterange import daterange
from pretix.helpers.plugin_enable import is_video_enabled

from ..utils import EventCreatedFor


class EventWidgetGenerator:
    """
    Generates dashboard widgets for events with advanced formatting and lazy loading.
    """

    @staticmethod
    def get_event_query(
        qs: QuerySet[Event], nmax: int, lazy: bool = False
    ) -> QuerySet[Event]:
        """
        Prepare event queryset with optimized loading.
        """
        if lazy:
            return qs[:nmax]

        return qs.prefetch_related(
            "_settings_objects", "organizer___settings_objects"
        ).select_related("organizer")[:nmax]

    @staticmethod
    def format_event_daterange(event: Event, tz: DstTzInfo) -> str:
        """
        Generate a formatted date range for an event.
        """
        if event.has_subevents:
            return (
                _("No dates")
                if event.min_from is None
                else daterange(
                    event.min_from.astimezone(tz),
                    (event.max_fromto or event.max_to or event.max_from).astimezone(tz),
                )
            )

        if event.date_to:
            return daterange(
                event.date_from.astimezone(tz), event.date_to.astimezone(tz)
            )

        return date_format(event.date_from.astimezone(tz), "DATE_FORMAT")

    @staticmethod
    def format_event_times(event: Event, tz: DstTzInfo, request: HttpRequest) -> str:
        """
        Generate a formatted time string for an event.
        """
        if event.has_subevents:
            return _("Event series")

        times = []

        # Add admission time if different from event start
        if event.date_admission and event.date_admission != event.date_from:
            times.append(
                date_format(event.date_admission.astimezone(tz), "TIME_FORMAT")
            )

        # Add event start time
        if event.date_from:
            times.append(date_format(event.date_from.astimezone(tz), "TIME_FORMAT"))

        formatted_times = " / ".join(times)

        # Add timezone indicator
        tzname = event.cache.get_or_set("timezone", lambda e=event: e.settings.timezone)
        if tzname != request.timezone and not event.has_subevents:
            formatted_times += f' <span class="fa fa-globe text-muted" data-toggle="tooltip" title="{tzname}"></span>'

        return formatted_times

    @staticmethod
    def generate_video_button(event: Event) -> str:
        """
        Generate a video button based on event configuration.
        """
        if is_video_enabled(event):
            url = reverse(
                "eventyay_common:event.create_access_to_video",
                kwargs={"event": event.slug, "organizer": event.organizer.slug},
            )
            return f'<a href="{url}" class="component">{_("Video")}</a>'
        return f"""
            <a href="#" data-toggle="modal" data-target="#alert-modal" class="component">
                {_("Video")}
            </a>
        """

    @staticmethod
    def generate_talk_button(event: Event) -> str:
        """
        Generate a talk button based on event settings.
        """
        if (
            event.settings.create_for == EventCreatedFor.BOTH.value
            or event.settings.talk_schedule_public is not None
        ):
            return f'<a href="{event.talk_dashboard_url}" class="middle-component">{_("Talks")}</a>'
        return f"""
            <a href="#" data-toggle="modal" data-target="#alert-modal" class="middle-component">
                {_("Talks")}
            </a>
        """

    @classmethod
    def generate_widget(
        cls, event: Event, request: HttpRequest, lazy: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a complete widget for an event.
        """
        widget_content = ""
        if not lazy:
            tzname = event.cache.get_or_set(
                "timezone", lambda e=event: e.settings.timezone
            )
            tz = pytz.timezone(tzname)

            widget_template = """
            <a href="{url}" class="event">
                <div class="name">{event}</div>
                <div class="daterange">{daterange}</div>
                <div class="times">{times}</div>
            </a>
            <div class="bottomrow">
                <a href="{ticket_url}" class="component">Tickets</a>
                {talk_button}
                {video_button}
            </div>
            """

            widget_content = widget_template.format(
                event=escape(event.name),
                times=cls.format_event_times(event, tz, request),
                daterange=cls.format_event_daterange(event, tz),
                url=reverse(
                    "eventyay_common:event.update",
                    kwargs={
                        "organizer": event.organizer.slug,
                        "event": event.slug,
                    },
                ),
                ticket_url=reverse(
                    "control:event.index",
                    kwargs={"event": event.slug, "organizer": event.organizer.slug},
                ),
                video_button=cls.generate_video_button(event),
                talk_button=cls.generate_talk_button(event),
            )

        return {
            "content": widget_content,
            "display_size": "small",
            "lazy": f"event-{event.pk}",
            "priority": 100,
            "container_class": "widget-container widget-container-event",
        }


def widgets_for_event_qs(
    request: HttpRequest, qs: QuerySet[Event], nmax: int, lazy: bool = False
) -> List[Dict[str, Any]]:
    """
    Generate event widgets for dashboard display.
    """
    events = EventWidgetGenerator.get_event_query(qs, nmax, lazy)

    return [
        EventWidgetGenerator.generate_widget(event, request, lazy) for event in events
    ]


def annotated_event_query(request: HttpRequest, lazy: bool = False) -> QuerySet[Event]:
    active_orders = (
        Order.objects.filter(
            event=OuterRef("pk"), status__in=[Order.STATUS_PENDING, Order.STATUS_PAID]
        )
        .order_by()
        .values("event")
        .annotate(c=Count("*"))
        .values("c")
    )

    required_actions = RequiredAction.objects.filter(event=OuterRef("pk"), done=False)
    qs = request.user.get_events_with_any_permission(request)
    if not lazy:
        qs = qs.annotate(
            order_count=Subquery(active_orders, output_field=IntegerField()),
            has_ra=Exists(required_actions),
        )
    qs = qs.annotate(
        min_from=Min("subevents__date_from"),
        max_from=Max("subevents__date_from"),
        max_to=Max("subevents__date_to"),
        max_fromto=Greatest(Max("subevents__date_to"), Max("subevents__date_from")),
    ).annotate(
        order_to=Coalesce("max_fromto", "max_to", "max_from", "date_to", "date_from"),
    )
    return qs


def rearrange(widgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort widget boxes according to priority.
    """
    mapping = {
        "small": 1,
        "big": 2,
        "full": 3,
    }

    def sort_key(element: Dict[str, Any]) -> Tuple[int, int]:
        return (
            element.get("priority", 1),
            mapping.get(element.get("display_size", "small"), 1),
        )

    return sorted(widgets, key=sort_key, reverse=True)


def eventyay_common_dashboard(request: HttpRequest) -> HttpResponse:
    widgets = []
    for r, result in user_dashboard_widgets.send(request, user=request.user):
        widgets.extend(result)
    ctx = {
        "widgets": rearrange(widgets),
        "can_create_event": request.user.teams.filter(can_create_events=True).exists(),
        "upcoming": widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True)
            .filter(
                Q(has_subevents=False)
                & Q(
                    Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                    | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
                )
            )
            .order_by("date_from", "order_to", "pk"),
            7,
            lazy=True,
        ),
        "past": widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True)
            .filter(
                Q(has_subevents=False)
                & Q(
                    Q(Q(date_to__isnull=True) & Q(date_from__lt=now()))
                    | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
                )
            )
            .order_by("-order_to", "pk"),
            8,
            lazy=True,
        ),
        "series": widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True)
            .filter(has_subevents=True)
            .order_by("-order_to", "pk"),
            8,
            lazy=True,
        ),
    }

    return render(request, "eventyay_common/dashboard/dashboard.html", ctx)


def user_index_widgets_lazy(request: HttpRequest) -> JsonResponse:
    widgets = []
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request)
        .filter(
            Q(has_subevents=False)
            & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
            )
        )
        .order_by("date_from", "order_to", "pk"),
        7,
    )
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request)
        .filter(
            Q(has_subevents=False)
            & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__lt=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
            )
        )
        .order_by("-order_to", "pk"),
        8,
    )
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request)
        .filter(has_subevents=True)
        .order_by("-order_to", "pk"),
        8,
    )
    return JsonResponse({"widgets": widgets})
