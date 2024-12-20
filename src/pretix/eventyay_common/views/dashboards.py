import contextlib
from datetime import timedelta

from django.http import JsonResponse
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import render
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from pretix.base.models import (
    Item, ItemCategory, Order, OrderRefund, Question, Quota, SubEvent, Voucher,
)
from pretix.base.timeline import timeline_for_event
from pretix.control.forms.event import CommentForm
from pretix.control.signals import event_dashboard_widgets

from ...base.models.orders import CancellationRequest

OVERVIEW_BANLIST = [
    'pretix.plugins.sendmail.order.email.sent'
]


def organiser_dashboard(request):
    context = {
        'ticket_component': settings.SITE_URL + '/control',
        'talk_component': settings.TALK_HOSTNAME + '/orga',
        'video_component': '#',
    }
    return render(request, 'eventyay_common/dashboard/dashboard.html', context)


def event_index_widgets_lazy(request, organizer, event):
    subevent = None
    if request.GET.get("subevent", "") != "" and request.event.has_subevents:
        i = request.GET.get("subevent", "")
        with contextlib.suppress(SubEvent.DoesNotExist):
            subevent = request.event.subevents.get(pk=i)

    widgets = []
    for r, result in event_dashboard_widgets.send(sender=request.event, subevent=subevent, lazy=False):
        widgets.extend(result)

    return JsonResponse({'widgets': widgets})


def event_index(request, organizer, event):
    subevent = None
    if request.GET.get("subevent", "") != "" and request.event.has_subevents:
        i = request.GET.get("subevent", "")
        with contextlib.suppress(SubEvent.DoesNotExist):
            subevent = request.event.subevents.get(pk=i)
    
    can_view_orders = request.user.has_event_permission(request.organizer, request.event, 'can_view_orders',
                                                        request=request)
    can_change_orders = request.user.has_event_permission(request.organizer, request.event, 'can_change_orders',
                                                          request=request)
    can_change_event_settings = request.user.has_event_permission(request.organizer, request.event,
                                                                  'can_change_event_settings', request=request)
    can_view_vouchers = request.user.has_event_permission(request.organizer, request.event, 'can_view_vouchers',
                                                          request=request)

    widgets = []
    if can_view_orders:
        for r, result in event_dashboard_widgets.send(sender=request.event, subevent=subevent, lazy=True):
            widgets.extend(result)

    qs = request.event.logentry_set.all().select_related('user', 'content_type', 'api_token', 'oauth_application',
                                                         'device').order_by('-datetime')
    qs = qs.exclude(action_type__in=OVERVIEW_BANLIST)
    if not can_view_orders:
        qs = qs.exclude(content_type=ContentType.objects.get_for_model(Order))
    if not can_view_vouchers:
        qs = qs.exclude(content_type=ContentType.objects.get_for_model(Voucher))
    if not can_change_event_settings:
        allowed_types = [
            ContentType.objects.get_for_model(Voucher),
            ContentType.objects.get_for_model(Order)
        ]
        if request.user.has_event_permission(request.organizer, request.event, 'can_change_items', request=request):
            allowed_types += [
                ContentType.objects.get_for_model(Item),
                ContentType.objects.get_for_model(ItemCategory),
                ContentType.objects.get_for_model(Quota),
                ContentType.objects.get_for_model(Question),
            ]
        qs = qs.filter(content_type__in=allowed_types)

    a_qs = request.event.requiredaction_set.filter(done=False)

    ctx = {
        'widgets': rearrange(widgets),
        'logs': qs[:5],
        'subevent': subevent,
        'actions': a_qs[:5] if can_change_orders else [],
        'comment_form': CommentForm(initial={'comment': request.event.comment}, readonly=not can_change_event_settings),
    }

    ctx['has_overpaid_orders'] = can_view_orders and Order.annotate_overpayments(request.event.orders).filter(
        Q(~Q(status=Order.STATUS_CANCELED) & Q(pending_sum_t__lt=0))
        | Q(Q(status=Order.STATUS_CANCELED) & Q(pending_sum_rc__lt=0))
    ).exists()
    ctx['has_pending_orders_with_full_payment'] = can_view_orders and Order.annotate_overpayments(request.event.orders).filter(
        Q(status__in=(Order.STATUS_EXPIRED, Order.STATUS_PENDING)) & Q(pending_sum_t__lte=0) & Q(require_approval=False)
    ).exists()
    ctx['has_pending_refunds'] = can_view_orders and OrderRefund.objects.filter(
        order__event=request.event,
        state__in=(OrderRefund.REFUND_STATE_CREATED, OrderRefund.REFUND_STATE_EXTERNAL)
    ).exists()
    ctx['has_pending_approvals'] = can_view_orders and request.event.orders.filter(
        status=Order.STATUS_PENDING,
        require_approval=True
    ).exists()
    ctx['has_cancellation_requests'] = can_view_orders and CancellationRequest.objects.filter(
        order__event=request.event
    ).exists()

    for a in ctx['actions']:
        a.display = a.display(request)

    ctx['timeline'] = [
        {
            'date': t.datetime.astimezone(request.event.timezone).date(),
            'entry': t,
            'time': t.datetime.astimezone(request.event.timezone)
        }
        for t in timeline_for_event(request.event, subevent)
    ]
    ctx['today'] = now().astimezone(request.event.timezone).date()
    ctx['nearly_now'] = now().astimezone(request.event.timezone) - timedelta(seconds=20)
    ctx['talk_edit_url'] = settings.TALK_HOSTNAME + '/orga/event/' + request.event.slug
    return render(request, 'eventyay_common/event/index.html', ctx)


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
