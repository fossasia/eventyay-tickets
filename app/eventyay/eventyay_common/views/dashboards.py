import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.core.exceptions import PermissionDenied
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
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import escape, format_html
from django.utils.timezone import now
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView


from eventyay.base.models import (
    Event,
    Product,
    ProductCategory,
    Order,
    OrderRefund,
    Question,
    Quota,
    RequiredAction,
    SubEvent,
    Voucher,
)
from eventyay.base.meetup import is_meetup_event
from eventyay.base.timeline import timeline_for_event
from eventyay.control.forms.event import CommentForm
from eventyay.control.signals import (
    event_dashboard_widgets,
    user_dashboard_widgets,
)
from eventyay.plugins.statistics.views import get_statistics_context
from eventyay.helpers.daterange import daterange
from eventyay.helpers.plugin_enable import is_video_enabled
from eventyay.multidomain.urlreverse import eventreverse

from .meetup import get_meetup_analytics_context

from ...base.models.orders import CancellationRequest
from ..onboarding import build_onboarding_context, build_organiser_dashboard_context, user_needs_onboarding
from ..permissions import (
    filter_timeline_entry_for_ticket_access,
    get_cached_event_dashboard_access,
    user_has_talk_dashboard_access,
    user_has_ticket_dashboard_access,
    user_has_video_dashboard_access,
)
from ..utils import EventCreatedFor, get_subevent

logger = logging.getLogger(__name__)

OVERVIEW_BANLIST = ['eventyay.plugins.sendmail.order.email.sent']

SHOP_STATE_WIDGET_KEY = 'shop_state'
# Widget producers that should remain visible to talk-only users must set
# ``key='shop_state'`` on their dashboard widget payload (see shop_state_widget).
EVENT_SETTINGS_PERMISSION_DIALOG_ID = 'event-settings-permission-dialog'
TICKET_PERMISSION_DIALOG_ID = 'ticket-permission-dialog'
TALK_PERMISSION_DIALOG_ID = 'talk-permission-dialog'
VIDEO_PERMISSION_DIALOG_ID = 'video-permission-dialog'


def _sanitize_widget_content_for_permission_dialog(content: str) -> str:
    """Return widget HTML safe to show inside a permission-dialog trigger."""
    if not content:
        return content
    soup = BeautifulSoup(content, 'html.parser')
    for a in soup.find_all('a'):
        a.unwrap()
    return str(soup).replace(gettext('Click here to change'), '')


def get_event_dashboard_widget_permissions(request: HttpRequest) -> dict[str, bool]:
    access = get_cached_event_dashboard_access(
        request, request.user, request.organizer, request.event
    )
    return {
        'has_ticket_dashboard_access': access['has_ticket_access'],
        'can_change_event_settings': access['can_change_event_settings'],
        'can_view_orders': access['can_view_orders'],
    }


def filter_event_dashboard_widgets_for_request(
    request: HttpRequest,  # kept for backward compatibility at call sites
    widgets: List[Dict[str, Any]] | None,
    permissions: dict[str, bool] | None = None,
) -> List[Dict[str, Any]]:
    if permissions is None:
        permissions = get_event_dashboard_widget_permissions(request)
    return filter_common_event_dashboard_widgets(
        widgets,
        has_ticket_dashboard_access=permissions['has_ticket_dashboard_access'],
        can_change_event_settings=permissions['can_change_event_settings'],
        can_view_orders=permissions.get('can_view_orders', False),
    )


# Widget ``lazy`` keys whose data comes from orders (attendees, revenue, etc.).
# These require ``can_view_orders`` even for users who have general ticket access.
_ORDER_DATA_WIDGET_LAZY_KEYS = (
    'attendees-ordered',
    'attendees-paid',
    'total-revenue',
)
_ORDER_DATA_WIDGET_LAZY_PREFIXES = (
    'waitinglist-',
    'checkin-',
)


def _is_order_data_widget(widget: Dict[str, Any]) -> bool:
    """Return True when a widget displays order-level data (attendees, revenue, etc.)."""
    lazy_key = widget.get('lazy', '')
    if lazy_key in _ORDER_DATA_WIDGET_LAZY_KEYS:
        return True
    return any(lazy_key.startswith(prefix) for prefix in _ORDER_DATA_WIDGET_LAZY_PREFIXES)


def filter_common_event_dashboard_widgets(
    widgets: List[Dict[str, Any]] | None,
    *,
    has_ticket_dashboard_access: bool,
    can_change_event_settings: bool,
    can_view_orders: bool = False,
) -> List[Dict[str, Any]]:
    """Limit dashboard widgets on the common event home for talk-only users.

    Users without ticket dashboard access only see widgets whose ``key`` is
    ``shop_state`` (ticket shop live status). Other widgets are omitted unless
    they declare that key or the user gains ticket dashboard access.

    Additionally, widgets that expose order data (attendee counts, revenue,
    waiting-list lengths, check-in stats) are suppressed for users who have
    generic ticket access (e.g. ``can_change_items``) but lack the specific
    ``can_view_orders`` permission.
    """
    if widgets is None:
        widgets = []
    elif isinstance(widgets, dict):
        widgets = [widgets]
    elif not isinstance(widgets, (list, tuple)):
        logger.warning(
            'Expected list of dashboard widgets, got %s',
            type(widgets).__name__,
        )
        widgets = []
    filtered: List[Dict[str, Any]] = []
    for widget in widgets:
        if not isinstance(widget, dict):
            continue
        widget = dict(widget)
        if not has_ticket_dashboard_access and widget.get('key') != SHOP_STATE_WIDGET_KEY:
            continue
        if widget.get('key') == SHOP_STATE_WIDGET_KEY and not can_change_event_settings:
            widget.pop('url', None)
            widget.pop('link', None)
            widget['content'] = _sanitize_widget_content_for_permission_dialog(widget.get('content', ''))
            widget['permission_dialog_id'] = EVENT_SETTINGS_PERMISSION_DIALOG_ID
        # Suppress order-data widgets (attendees, revenue, etc.) for users
        # who have ticket dashboard access but not can_view_orders.
        if not can_view_orders and _is_order_data_widget(widget):
            continue
        filtered.append(widget)
    return filtered


def event_index_widgets_lazy(request: HttpRequest, **kwargs) -> JsonResponse:
    subevent = get_subevent(request)
    permissions = get_event_dashboard_widget_permissions(request)

    widgets: List[Dict[str, Any]] = []
    for r, result in event_dashboard_widgets.send(
        sender=request.event,
        subevent=subevent,
        lazy=False,
        request=request,
    ):
        widgets.extend(filter_event_dashboard_widgets_for_request(request, result, permissions))

    return JsonResponse({'widgets': widgets})


class EventIndexView(TemplateView):
    """
    A class-based view for rendering the event index dashboard.
    """

    template_name = 'eventyay_common/event/index.html'

    def get_template_names(self):
        if is_meetup_event(self.request.event):
            return ['eventyay_common/event/meetup_dashboard.html']
        return [self.template_name]

    def render_to_response(self, context, **response_kwargs):
        resp = super().render_to_response(context, **response_kwargs)
        if context.get('can_view_orders') and context.get('stats_has_orders'):
            resp['Content-Security-Policy'] = "script-src 'unsafe-eval'; style-src 'unsafe-inline'"
            resp._csp_update = {'script-src': ["'unsafe-eval'"], 'style-src': ["'unsafe-inline'"]}
        return resp

    @staticmethod
    def rearrange(widgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort widget boxes according to priority.
        """
        mapping = {
            'small': 1,
            'big': 2,
            'full': 3,
        }

        def sort_key(element: Dict[str, Any]) -> tuple:
            return (
                element.get('priority', 1),
                mapping.get(element.get('display_size', 'small'), 1),
            )

        return sorted(widgets, key=sort_key, reverse=True)

    def _get_user_permissions(self) -> Dict[str, bool]:
        """
        Centralize permission checks for the event.
        """
        request = self.request
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

    def _collect_dashboard_widgets(self, subevent: Optional[SubEvent]) -> List[Dict[str, Any]]:
        """
        Collect and filter dashboard widgets based on permissions.

        Talk-only users see the event live-status widget but not ticket metrics.
        """
        request = self.request
        widget_permissions = get_event_dashboard_widget_permissions(request)
        widgets: List[Dict[str, Any]] = []
        for caller, result in event_dashboard_widgets.send(
            sender=request.event,
            subevent=subevent,
            lazy=True,
            request=request,
        ):
            widgets.extend(
                filter_event_dashboard_widgets_for_request(request, result, widget_permissions)
            )
        return self.rearrange(widgets)

    def _filter_log_entries(self, qs: QuerySet, permissions: Dict[str, bool]) -> QuerySet:
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

            if permissions['can_change_items']:
                allowed_types += [
                    ContentType.objects.get_for_model(Product),
                    ContentType.objects.get_for_model(ProductCategory),
                    ContentType.objects.get_for_model(Quota),
                    ContentType.objects.get_for_model(Question),
                ]

            qs = qs.filter(content_type__in=allowed_types)

        return qs

    def _check_event_statuses(self, can_view_orders: bool) -> Dict[str, Any]:
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
        widgets = self._collect_dashboard_widgets(subevent)

        # Filter log entries
        qs = (
            request.event.logentry_set.all()
            .select_related('user', 'content_type', 'api_token', 'oauth_application', 'device')
            .order_by('-datetime')
        )
        qs = self._filter_log_entries(qs, permissions)

        access = get_cached_event_dashboard_access(
            request, request.user, request.organizer, request.event
        )
        can_view_orders = permissions['can_view_orders']

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
                'is_video_enabled': is_video_enabled(request.event),
                'can_change_event_settings': permissions['can_change_event_settings'],
                'can_view_orders': can_view_orders,
                **self._check_event_statuses(can_view_orders),
            }
        )

        if is_meetup_event(request.event):
            if can_view_orders:
                tz = ZoneInfo(request.event.timezone)
                context.update(get_meetup_analytics_context(request.event, tz=tz))
        elif can_view_orders:
            context.update(get_statistics_context(request, subevent=subevent))

        # Process actions
        for action in context['actions']:
            action.display = action.display(request)

        # Add timeline information
        context['timeline'] = [
            {
                'date': t.datetime.astimezone(ZoneInfo(request.event.timezone)).date(),
                'entry': filter_timeline_entry_for_ticket_access(t, access['has_ticket_access']),
                'time': t.datetime.astimezone(ZoneInfo(request.event.timezone)),
            }
            for t in timeline_for_event(request.event, subevent)
        ]

        context['today'] = now().astimezone(ZoneInfo(request.event.timezone)).date()
        context['nearly_now'] = now().astimezone(ZoneInfo(request.event.timezone)) - timedelta(seconds=20)
        context['organizer_teams'] = request.event.teams.values_list('id', 'name')
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.has_event_permission(
            request.organizer, request.event, 'can_change_event_settings', request=request
        ):
            messages.error(request, _("You do not have permission to change event settings."))
            return redirect(self.get_success_url())

        if 'toggle_video_visibility' in request.POST:
            current_setting = request.event.settings.get('venueless_show_public_link', False)
            new_setting = not current_setting
            request.event.settings.set('venueless_show_public_link', new_setting)

            if new_setting:
                messages.success(request, _("Video link is now visible on public pages."))
            else:
                messages.success(request, _("Video link is now hidden from public pages."))

            return redirect(self.get_success_url())

        return self.get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'eventyay_common:event.index',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


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
    def format_event_daterange(event: Event, tz: ZoneInfo) -> str:
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
    def format_event_times(event: Event, tz: ZoneInfo, request: HttpRequest) -> str:
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
    def generate_video_button(event: Event, request: HttpRequest) -> str:
        """
        Generate a video button based on the user's video permissions.
        The access view will ensure configuration and plugin setup as needed.
        """
        has_video_access = user_has_video_dashboard_access(
            request.user, event.organizer, event, request=request
        )
        if has_video_access:
            url = reverse(
                'eventyay_common:event.create_access_to_video',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            )
            return f'<a href="{url}" class="component">{_("Video")}</a>'

        return format_html(
            '<a href="#" role="button" class="component" aria-haspopup="dialog" '
            'aria-controls="{}" data-dialog-target="#{}" data-toggle="dialog">{}</a>',
            VIDEO_PERMISSION_DIALOG_ID,
            VIDEO_PERMISSION_DIALOG_ID,
            _('Video'),
        )

    @staticmethod
    def generate_talk_button(event: Event, request: HttpRequest) -> str:
        """
        Generate a talk button based on event settings and user permission.
        """
        if event.settings.create_for != EventCreatedFor.BOTH.value and event.settings.talk_schedule_public is None:
            return format_html(
                '<a href="#" data-toggle="modal" data-target="#alert-modal" class="middle-component">{}</a>',
                _('Talks'),
            )

        has_talk_access = user_has_talk_dashboard_access(
            request.user, event.organizer, event, request=request
        )
        if not has_talk_access:
            return format_html(
                '<a href="#" class="middle-component" role="button" aria-haspopup="dialog" '
                'aria-controls="{}" data-dialog-target="#{}" data-toggle="dialog">{}</a>',
                TALK_PERMISSION_DIALOG_ID,
                TALK_PERMISSION_DIALOG_ID,
                _('Talks'),
            )

        talk_url = reverse('orga:event.dashboard', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
        return format_html(
            '<a href="{}" class="middle-component">{}</a>',
            talk_url,
            _('Talks'),
        )

    @staticmethod
    def generate_ticket_button(event: Event, request: HttpRequest) -> str:
        """
        Generate a ticket button based on the user's ticket permissions.

        Users without ticket permissions see a modal trigger instead of a link.
        """
        has_ticket_access = user_has_ticket_dashboard_access(
            request.user, event.organizer, event, request=request
        )
        if has_ticket_access:
            ticket_url = reverse(
                'control:event.index',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            )
            return format_html(
                '<a href="{}" class="component">{}</a>',
                ticket_url,
                _('Tickets'),
            )
        return format_html(
            '<a href="#" role="button" class="component" aria-haspopup="dialog" '
            'aria-controls="{}" data-dialog-target="#{}" data-toggle="dialog">{}</a>',
            TICKET_PERMISSION_DIALOG_ID,
            TICKET_PERMISSION_DIALOG_ID,
            _('Tickets'),
        )

    @classmethod
    def generate_widget(cls, event: Event, request: HttpRequest, lazy: bool = False) -> Dict[str, Any]:
        """
        Generate a complete widget for an event.
        """
        widget_content = ''
        if not lazy:
            tzname = event.cache.get_or_set('timezone', lambda e=event: e.settings.timezone)
            tz = ZoneInfo(tzname)

            widget_template = """
            <a href="{url}" class="event">
                <div class="name">{event}</div>
                <div class="daterange">{daterange}</div>
                <div class="times">{times}</div>
            </a>
            <div class="bottomrow">
                {ticket_button}
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
                ticket_button=cls.generate_ticket_button(event, request),
                video_button=cls.generate_video_button(event, request),
                talk_button=cls.generate_talk_button(event, request),
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
) -> List[Dict[str, Any]]:
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


def rearrange(widgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort widget boxes according to priority.
    """
    mapping = {
        'small': 1,
        'big': 2,
        'full': 3,
    }

    def sort_key(element: Dict[str, Any]) -> Tuple[int, int]:
        return (
            element.get('priority', 1),
            mapping.get(element.get('display_size', 'small'), 1),
        )

    return sorted(widgets, key=sort_key, reverse=True)


def eventyay_common_dashboard(request: HttpRequest) -> HttpResponse:
    if user_needs_onboarding(request.user, request):
        ctx = build_onboarding_context(request)
        return render(request, 'eventyay_common/dashboard/dashboard.html', ctx)

    widgets = []
    for r, result in user_dashboard_widgets.send(request, user=request.user):
        widgets.extend(result)

    ctx = build_organiser_dashboard_context(request, annotated_event_query)
    ctx['widgets'] = rearrange(widgets)
    ctx['video_permission_dialog_id'] = VIDEO_PERMISSION_DIALOG_ID
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
