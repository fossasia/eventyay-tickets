from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.timezone import now
from i18nfield.strings import LazyI18nString

from pretix.base.models import Order, Event
from pretix.base.reldate import RelativeDateWrapper
from pretix.base.settings import settings_hierarkey
from pretix.base.signals import event_copy_data, item_copy_data
from pretix.control.signals import nav_event_settings
from pretix.presale.signals import order_info_top, position_info_top


@receiver(order_info_top, dispatch_uid="venueless_order_info")
def w_order_info(sender: Event, request, order: Order, **kwargs):
    if (
            (order.status != Order.STATUS_PAID and not (order.status == Order.STATUS_PENDING and
                                                        sender.settings.venueless_allow_pending))
            or not order.positions.exists() or not sender.settings.venueless_secret
    ):
        return

    positions = [
        p for p in order.positions.filter(
            item__admission=True, addon_to__isnull=True
        )
    ]
    positions = [
        p for p in positions
        if (
                not sender.settings.venueless_start or sender.settings.venueless_start.datetime(p.subevent or sender) <= now()
        ) and (
            sender.settings.venueless_all_items or p.item_id in (p.event.settings.venueless_items or[])
        )
    ]
    if not positions:
        return

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
            or (
                not sender.settings.venueless_all_items and position.item_id not in (position.event.settings.venueless_items or [])
            )
            or not sender.settings.venueless_secret
    ):
        return
    if sender.settings.venueless_start and sender.settings.venueless_start.datetime(position.subevent or sender) > now():
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


@receiver(signal=event_copy_data, dispatch_uid="venueless_event_copy_data")
def event_copy_data_r(sender, other, item_map, question_map, **kwargs):
    sender.settings['venueless_items'] = [
        item_map[item].pk for item in other.settings.get('venueless_items', default=[]) if item in item_map
    ]
    sender.settings['venueless_questions'] = [
        question_map[q].pk for q in other.settings.get('venueless_questions', default=[]) if q in question_map
    ]


@receiver(signal=item_copy_data, dispatch_uid="venueless_item_copy_data")
def item_copy_data_r(sender, source, target, **kwargs):
    items = sender.settings.get('venueless_items') or []
    items.append(target.pk)
    sender.settings['venueless_items'] = items


settings_hierarkey.add_default('venueless_start', None, RelativeDateWrapper)
settings_hierarkey.add_default('venueless_text', None, LazyI18nString)
settings_hierarkey.add_default('venueless_allow_pending', 'False', bool)
settings_hierarkey.add_default('venueless_all_items', 'True', bool)
settings_hierarkey.add_default('venueless_items', '[]', list)
settings_hierarkey.add_default('venueless_questions', '[]', list)
