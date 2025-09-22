from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytz
from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    Count,
    Exists,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
)
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import escape
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from pytz.tzinfo import DstTzInfo

from eventyay.base.models import (
    Event,
    Order,
    OrderRefund,
    Product,
    ProductCategory,
    Question,
    Quota,
    RequiredAction,
    SubEvent,
    Voucher,
)
from eventyay.base.timeline import timeline_for_event
from eventyay.control.forms.event import CommentForm
from eventyay.control.signals import (
    event_dashboard_widgets,
    user_dashboard_widgets,
)
from eventyay.helpers.daterange import daterange
from eventyay.helpers.plugin_enable import is_video_enabled

from ...base.models.orders import CancellationRequest
from ..utils import EventCreatedFor, get_subevent


OVERVIEW_BANLIST = ['pretix.plugins.sendmail.order.email.sent']


def event_index_widgets_lazy(request: HttpRequest, **kwargs) -> JsonResponse:
    subevent = get_subevent(request)

    widgets = []
    for r, result in event_dashboard_widgets.send(sender=request.event, subevent=subevent, lazy=False):
        widgets.extend(result)

    return JsonResponse({'widgets': widgets})


class EventIndexView(TemplateView):
    """
    A class-based view for rendering the event index dashboard.
    """

    template_name = 'eventyay_common/event/index.html'

    @staticmethod
    def rearrange(widgets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Sort widget boxes according to priority.
        """
        mapping = {
            'small': 1,
            'big': 2,
            'full': 3,
        }

        def sort_key(element: dict[str, Any]) -> tuple:
            return (
                element.get('priority', 1),
                mapping.get(element.get('display_size', 'small'), 1),
            )

        return sorted(widgets, key=sort_key, reverse=True)

    def _get_user_permissions(self) -> dict[str, bool]:
        """
        Centralize permission checks for the event.
        """
        request = self.request
        print('\n', request, '\n')
        return {
            'can_view_orders': request.user.has_event_permission(
                request.organizer, request.event, 'can_view_orders', request=request
            ),
            'can_change_orders': request.user.has_event_permission(
                request.organizer, request.event, 'can_change_orders', request=request
            ),
            'can_change_event_settings': request.user.has_event_permission(
                request.organizer,
                request.event,
                'can_change_event_settings',
                request=request,
            ),
            'can_view_vouchers': request.user.has_event_permission(
                request.organizer, request.event, 'can_view_vouchers', request=request
            ),
            'can_change_items': request.user.has_event_permission(
                request.organizer, request.event, 'can_change_items', request=request
            ),
        }

    def _collect_dashboard_widgets(self, subevent: SubEvent | None, can_view_orders: bool) -> list[dict[str, Any]]:
        """
        Collect and filter dashboard widgets based on permissions.
        """
        if not can_view_orders:
            return []

        request = self.request
        widgets = []
        for caller, result in event_dashboard_widgets.send(sender=request.event, subevent=subevent, lazy=True):
            widgets.extend(result)
        return self.rearrange(widgets)

    def _filter_log_entries(self, qs: QuerySet, permissions: dict[str, bool]) -> QuerySet:
        """
        Apply log entry filtering based on user permissions.

        :param qs: Queryset of log entries
        :param permissions: Dictionary of user permissions
        :return: Filtered queryset
        """
        qs = qs.exclude(action_type__in=OVERVIEW_BANLIST)

        if not permissions['can_view_orders']:
            qs = qs.exclude(content_type=ContentType.objects.get_for_model(Order))

        if not permissions['can_view_vouchers']:
            qs = qs.exclude(content_type=ContentType.objects.get_for_model(Voucher))

        if not permissions['can_change_event_settings']:
            allowed_types = [
                ContentType.objects.get_for_model(Voucher),
                ContentType.objects.get_for_model(Order),
            ]

            if permissions['can_change_products']:
                allowed_types += [
                    ContentType.objects.get_for_model(Product),
                    ContentType.objects.get_for_model(ProductCategory),
                    ContentType.objects.get_for_model(Quota),
                    ContentType.objects.get_for_model(Question),
                ]

            qs = qs.filter(content_type__in=allowed_types)

        return qs

    def _check_event_statuses(self, can_view_orders: bool) -> dict[str, Any]:
        """
        Centralize various event status checks.
        """
        request = self.request
        return {
            'has_overpaid_orders': can_view_orders
            and Order.annotate_overpayments(request.event.orders)
            .filter(
                Q(~Q(status=Order.STATUS_CANCELED) & Q(pending_sum_t__lt=0))
                | Q(Q(status=Order.STATUS_CANCELED) & Q(pending_sum_rc__lt=0))
            )
            .exists(),
            'has_pending_orders_with_full_payment': can_view_orders
            and Order.annotate_overpayments(request.event.orders)
            .filter(
                Q(status__in=(Order.STATUS_EXPIRED, Order.STATUS_PENDING))
                & Q(pending_sum_t__lte=0)
                & Q(require_approval=False)
            )
            .exists(),
            'has_pending_refunds': can_view_orders
            and OrderRefund.objects.filter(
                order__event=request.event,
                state__in=(
                    OrderRefund.REFUND_STATE_CREATED,
                    OrderRefund.REFUND_STATE_EXTERNAL,
                ),
            ).exists(),
            'has_pending_approvals': can_view_orders
            and request.event.orders.filter(status=Order.STATUS_PENDING, require_approval=True).exists(),
            'has_cancellation_requests': can_view_orders
            and CancellationRequest.objects.filter(order__event=request.event).exists(),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # Get subevent and permissions
        subevent = get_subevent(request)
        permissions = self._get_user_permissions()

        # Collect widgets
        widgets = self._collect_dashboard_widgets(subevent, permissions['can_view_orders'])

        # Filter log entries
        qs = (
            request.event.logentry_set.all()
            .select_related('user', 'content_type', 'api_token', 'oauth_application', 'device')
            .order_by('-datetime')
        )
        qs = self._filter_log_entries(qs, permissions)

        # Prepare context
        context.update(
            {
                'widgets': widgets,
                'logs': qs[:5],
                'subevent': subevent,
                'actions': (
                    request.event.requiredaction_set.filter(done=False)[:5] if permissions['can_change_orders'] else []
                ),
                'comment_form': CommentForm(
                    initial={'comment': request.event.comment},
                    readonly=not permissions['can_change_event_settings'],
                ),
                **self._check_event_statuses(permissions['can_view_orders']),
            }
        )

        # Process actions
        for action in context['actions']:
            action.display = action.display(request)

        # Add timeline information
        context['timeline'] = [
            {
                'date': t.datetime.astimezone(ZoneInfo(request.event.timezone)).date(),
                'entry': t,
                'time': t.datetime.astimezone(ZoneInfo(request.event.timezone)),
            }
            for t in timeline_for_event(request.event, subevent)
        ]

        context['today'] = now().astimezone(ZoneInfo(request.event.timezone)).date()
        context['nearly_now'] = now().astimezone(ZoneInfo(request.event.timezone)) - timedelta(seconds=20)

        return context


class EventWidgetGenerator:
    """
    Generates dashboard widgets for events with advanced formatting and lazy loading.
    """

    @staticmethod
    def get_event_query(qs: QuerySet[Event], nmax: int, lazy: bool = False) -> QuerySet[Event]:
        """
        Prepare event queryset with optimized loading.
        """
        if lazy:
            return qs[:nmax]

        return qs.prefetch_related('_settings_objects', 'organizer___settings_objects').select_related('organizer')[
            :nmax
        ]

    @staticmethod
    def format_event_daterange(event: Event, tz: DstTzInfo) -> str:
        """
        Generate a formatted date range for an event.
        """
        if event.has_subevents:
            return (
                _('No dates')
                if event.min_from is None
                else daterange(
                    event.min_from.astimezone(tz),
                    (event.max_fromto or event.max_to or event.max_from).astimezone(tz),
                )
            )

        if event.date_to:
            return daterange(event.date_from.astimezone(tz), event.date_to.astimezone(tz))

        return date_format(event.date_from.astimezone(tz), 'DATE_FORMAT')

    @staticmethod
    def format_event_times(event: Event, tz: DstTzInfo, request: HttpRequest) -> str:
        """
        Generate a formatted time string for an event.
        """
        if event.has_subevents:
            return _('Event series')

        times = []

        # Add admission time if different from event start
        if event.date_admission and event.date_admission != event.date_from:
            times.append(date_format(event.date_admission.astimezone(tz), 'TIME_FORMAT'))

        # Add event start time
        if event.date_from:
            times.append(date_format(event.date_from.astimezone(tz), 'TIME_FORMAT'))

        formatted_times = ' / '.join(times)

        # Add timezone indicator
        tzname = event.cache.get_or_set('timezone', lambda e=event: e.settings.timezone)
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
                'eventyay_common:event.create_access_to_video',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            )
            return f'<a href="{url}" class="component">{_("Video")}</a>'
        return f"""
            <a href="#" data-toggle="modal" data-target="#alert-modal" class="component">
                {_('Video')}
            </a>
        """

    @staticmethod
    def generate_talk_button(event: Event) -> str:
        """
        Generate a talk button based on event settings.
        """
        if event.settings.create_for == EventCreatedFor.BOTH.value or event.settings.talk_schedule_public is not None:
            return f'<a href="{event.talk_dashboard_url}" class="middle-component">{_("Talks")}</a>'
        return f"""
            <a href="#" data-toggle="modal" data-target="#alert-modal" class="middle-component">
                {_('Talks')}
            </a>
        """

    @classmethod
    def generate_widget(cls, event: Event, request: HttpRequest, lazy: bool = False) -> dict[str, Any]:
        """
        Generate a complete widget for an event.
        """
        widget_content = ''
        if not lazy:
            tzname = event.cache.get_or_set('timezone', lambda e=event: e.settings.timezone)
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
                    'eventyay_common:event.index',
                    kwargs={
                        'organizer': event.organizer.slug,
                        'event': event.slug,
                    },
                ),
                ticket_url=reverse(
                    'control:event.index',
                    kwargs={'event': event.slug, 'organizer': event.organizer.slug},
                ),
                video_button=cls.generate_video_button(event),
                talk_button=cls.generate_talk_button(event),
            )

        return {
            'content': widget_content,
            'display_size': 'small',
            'lazy': f'event-{event.pk}',
            'priority': 100,
            'container_class': 'widget-container widget-container-event',
        }


def widgets_for_event_qs(
    request: HttpRequest, qs: QuerySet[Event], nmax: int, lazy: bool = False
) -> list[dict[str, Any]]:
    """
    Generate event widgets for dashboard display.
    """
    events = EventWidgetGenerator.get_event_query(qs, nmax, lazy)

    return [EventWidgetGenerator.generate_widget(event, request, lazy) for event in events]


def annotated_event_query(request: HttpRequest, lazy: bool = False) -> QuerySet[Event]:
    active_orders = (
        Order.objects.filter(event=OuterRef('pk'), status__in=[Order.STATUS_PENDING, Order.STATUS_PAID])
        .order_by()
        .values('event')
        .annotate(c=Count('*'))
        .values('c')
    )

    required_actions = RequiredAction.objects.filter(event=OuterRef('pk'), done=False)
    qs = request.user.get_events_with_any_permission(request)
    if not lazy:
        qs = qs.annotate(
            order_count=Subquery(active_orders, output_field=IntegerField()),
            has_ra=Exists(required_actions),
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


def rearrange(widgets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sort widget boxes according to priority.
    """
    mapping = {
        'small': 1,
        'big': 2,
        'full': 3,
    }

    def sort_key(element: dict[str, Any]) -> tuple[int, int]:
        return (
            element.get('priority', 1),
            mapping.get(element.get('display_size', 'small'), 1),
        )

    return sorted(widgets, key=sort_key, reverse=True)


def eventyay_common_dashboard(request: HttpRequest) -> HttpResponse:
    widgets = []
    for r, result in user_dashboard_widgets.send(request, user=request.user):
        widgets.extend(result)
    ctx = {
        'widgets': rearrange(widgets),
        'can_create_event': request.user.teams.filter(can_create_events=True).exists(),
        'upcoming': widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True)
            .filter(
                Q(has_subevents=False)
                & Q(
                    Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                    | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
                )
            )
            .order_by('date_from', 'order_to', 'pk'),
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
            )
            .order_by('-order_to', 'pk'),
            8,
            lazy=True,
        ),
        'series': widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True).filter(has_subevents=True).order_by('-order_to', 'pk'),
            8,
            lazy=True,
        ),
    }

    return render(request, 'eventyay_common/dashboard/dashboard.html', ctx)


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
        .order_by('date_from', 'order_to', 'pk'),
        7,
    )
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request)
        .filter(
            Q(has_subevents=False)
            & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__lt=now())) | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
            )
        )
        .order_by('-order_to', 'pk'),
        8,
    )
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request).filter(has_subevents=True).order_by('-order_to', 'pk'),
        8,
    )
    return JsonResponse({'widgets': widgets})
