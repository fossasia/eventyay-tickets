from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, QuerySet
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.utils.timezone import now
from django.views.generic import TemplateView

from pretix.base.models import (
    Item, ItemCategory, Order, OrderRefund, Question, Quota, SubEvent, Voucher,
)
from pretix.base.timeline import timeline_for_event
from pretix.control.forms.event import CommentForm
from pretix.control.signals import event_dashboard_widgets

from ...base.models.orders import CancellationRequest
from ..utils import get_subevent

OVERVIEW_BANLIST = ["pretix.plugins.sendmail.order.email.sent"]


def organiser_dashboard(request):
    context = {
        "ticket_component": settings.SITE_URL + "/control",
        "talk_component": settings.TALK_HOSTNAME + "/orga",
        "video_component": "#",
    }
    return render(request, "eventyay_common/dashboard/dashboard.html", context)


def event_index_widgets_lazy(request: HttpRequest, **kwargs) -> JsonResponse:
    subevent = get_subevent(request)

    widgets = []
    for r, result in event_dashboard_widgets.send(
        sender=request.event, subevent=subevent, lazy=False
    ):
        widgets.extend(result)

    return JsonResponse({"widgets": widgets})


class EventIndexView(TemplateView):
    """
    A class-based view for rendering the event index dashboard.
    """

    template_name = "eventyay_common/event/index.html"

    @staticmethod
    def rearrange(widgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort widget boxes according to priority.
        """
        mapping = {
            "small": 1,
            "big": 2,
            "full": 3,
        }

        def sort_key(element: Dict[str, Any]) -> tuple:
            return (
                element.get("priority", 1),
                mapping.get(element.get("display_size", "small"), 1),
            )

        return sorted(widgets, key=sort_key, reverse=True)

    def _get_user_permissions(self) -> Dict[str, bool]:
        """
        Centralize permission checks for the event.
        """
        request = self.request
        return {
            "can_view_orders": request.user.has_event_permission(
                request.organizer, request.event, "can_view_orders", request=request
            ),
            "can_change_orders": request.user.has_event_permission(
                request.organizer, request.event, "can_change_orders", request=request
            ),
            "can_change_event_settings": request.user.has_event_permission(
                request.organizer,
                request.event,
                "can_change_event_settings",
                request=request,
            ),
            "can_view_vouchers": request.user.has_event_permission(
                request.organizer, request.event, "can_view_vouchers", request=request
            ),
            "can_change_items": request.user.has_event_permission(
                request.organizer, request.event, "can_change_items", request=request
            ),
        }

    def _collect_dashboard_widgets(
        self, subevent: Optional[SubEvent], can_view_orders: bool
    ) -> List[Dict[str, Any]]:
        """
        Collect and filter dashboard widgets based on permissions.
        """
        if not can_view_orders:
            return []

        request = self.request
        widgets = []
        for _, result in event_dashboard_widgets.send(
            sender=request.event, subevent=subevent, lazy=True
        ):
            widgets.extend(result)
        return self.rearrange(widgets)

    def _filter_log_entries(
        self, qs: QuerySet, permissions: Dict[str, bool]
    ) -> QuerySet:
        """
        Apply log entry filtering based on user permissions.

        :param qs: Queryset of log entries
        :param permissions: Dictionary of user permissions
        :return: Filtered queryset
        """
        qs = qs.exclude(action_type__in=OVERVIEW_BANLIST)

        if not permissions["can_view_orders"]:
            qs = qs.exclude(content_type=ContentType.objects.get_for_model(Order))

        if not permissions["can_view_vouchers"]:
            qs = qs.exclude(content_type=ContentType.objects.get_for_model(Voucher))

        if not permissions["can_change_event_settings"]:
            allowed_types = [
                ContentType.objects.get_for_model(Voucher),
                ContentType.objects.get_for_model(Order),
            ]

            if permissions["can_change_items"]:
                allowed_types += [
                    ContentType.objects.get_for_model(Item),
                    ContentType.objects.get_for_model(ItemCategory),
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
            "has_overpaid_orders": can_view_orders
            and Order.annotate_overpayments(request.event.orders)
            .filter(
                Q(~Q(status=Order.STATUS_CANCELED) & Q(pending_sum_t__lt=0))
                | Q(Q(status=Order.STATUS_CANCELED) & Q(pending_sum_rc__lt=0))
            )
            .exists(),
            "has_pending_orders_with_full_payment": can_view_orders
            and Order.annotate_overpayments(request.event.orders)
            .filter(
                Q(status__in=(Order.STATUS_EXPIRED, Order.STATUS_PENDING))
                & Q(pending_sum_t__lte=0)
                & Q(require_approval=False)
            )
            .exists(),
            "has_pending_refunds": can_view_orders
            and OrderRefund.objects.filter(
                order__event=request.event,
                state__in=(
                    OrderRefund.REFUND_STATE_CREATED,
                    OrderRefund.REFUND_STATE_EXTERNAL,
                ),
            ).exists(),
            "has_pending_approvals": can_view_orders
            and request.event.orders.filter(
                status=Order.STATUS_PENDING, require_approval=True
            ).exists(),
            "has_cancellation_requests": can_view_orders
            and CancellationRequest.objects.filter(order__event=request.event).exists(),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # Get subevent and permissions
        subevent = get_subevent(request)
        permissions = self._get_user_permissions()

        # Collect widgets
        widgets = self._collect_dashboard_widgets(
            subevent, permissions["can_view_orders"]
        )

        # Filter log entries
        qs = (
            request.event.logentry_set.all()
            .select_related(
                "user", "content_type", "api_token", "oauth_application", "device"
            )
            .order_by("-datetime")
        )
        qs = self._filter_log_entries(qs, permissions)

        # Prepare context
        context.update(
            {
                "widgets": widgets,
                "logs": qs[:5],
                "subevent": subevent,
                "actions": (
                    request.event.requiredaction_set.filter(done=False)[:5]
                    if permissions["can_change_orders"]
                    else []
                ),
                "comment_form": CommentForm(
                    initial={"comment": request.event.comment},
                    readonly=not permissions["can_change_event_settings"],
                ),
                **self._check_event_statuses(permissions["can_view_orders"]),
            }
        )

        # Process actions
        for action in context["actions"]:
            action.display = action.display(request)

        # Add timeline information
        context["timeline"] = [
            {
                "date": t.datetime.astimezone(request.event.timezone).date(),
                "entry": t,
                "time": t.datetime.astimezone(request.event.timezone),
            }
            for t in timeline_for_event(request.event, subevent)
        ]

        context["today"] = now().astimezone(request.event.timezone).date()
        context["nearly_now"] = now().astimezone(request.event.timezone) - timedelta(
            seconds=20
        )

        return context
