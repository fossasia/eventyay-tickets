from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.timezone import now

from pretix.base.models import Order, Event
from pretix.base.reldate import RelativeDateWrapper
from pretix.base.settings import settings_hierarkey
from pretix.control.signals import nav_event_settings
from pretix.presale.signals import order_info_top, position_info_top


@receiver(order_info_top, dispatch_uid="venueless_order_info")
def w_order_info(sender: Event, request, order: Order, **kwargs):
    if (
            (order.status != Order.STATUS_PAID and not (order.status == Order.STATUS_PENDING and
                                                        sender.settings.venueless_allow_pending))
            or not order.positions.exists()
    ):
        return

    positions = [
        p for p in order.positions.filter(
            item__admission=True
        )
    ]
    if not positions:
        return
    positions = [
        p for p in positions
        if not sender.settings.venueless_start or sender.settings.venueless.datetime(p.subevent or sender) <= now()
    ]

    template = get_template('pretix_venueless/order_info.html')
    ctx = {
        'order': order,
        'event': sender,
        'positions': positions,
    }
    return template.render(ctx, request=request)


@receiver(position_info_top, dispatch_uid="venueless_position_info")
def w_pos_info(sender: Event, request, order: Order, position, **kwargs):
    if (
            (order.status != Order.STATUS_PAID and not (order.status == Order.STATUS_PENDING and
                                                        sender.settings.venueless_allow_pending))
            or not order.positions.exists()
            or position.canceled
            or not position.item.admission
    ):
        return
    if sender.settings.venueless_start and sender.settings.venueless.datetime(position.subevent or sender) > now():
        positions = []
    else:
        positions = [position]
    template = get_template('pretix_venueless/order_info.html')
    ctx = {
        'order': order,
        'event': sender,
        'positions': positions,
    }
    return template.render(ctx, request=request)


@receiver(nav_event_settings, dispatch_uid='venueless_nav')
def navbar_info(sender, request, **kwargs):
    url = resolve(request.path_info)
    if not request.user.has_event_permission(request.organizer, request.event, 'can_change_event_settings',
                                             request=request):
        return []
    return [{
        'label': 'Venueless',
        'url': reverse('plugins:pretix_venueless:settings', kwargs={
            'event': request.event.slug,
            'organizer': request.organizer.slug,
        }),
        'active': url.namespace == 'plugins:pretix_venueless',
    }]


settings_hierarkey.add_default('venueless_start', None, RelativeDateWrapper)
settings_hierarkey.add_default('venueless_allow_pending', 'False', bool)
