from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from i18nfield.strings import LazyI18nString
from pretix.base.models import Event, Order
from pretix.base.reldate import RelativeDateWrapper
from pretix.base.settings import settings_hierarkey
from pretix.base.signals import event_copy_data, item_copy_data
from pretix.control.signals import nav_event, nav_event_settings
from pretix.presale.signals import order_info_top, position_info_top


@receiver(nav_event, dispatch_uid="exhibitors_nav")
def control_nav_import(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    return [
        {
            'label': _('Exhibitors'),
            'url': reverse(
                'plugins:exhibitors:info',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.event.organizer.slug,
                }
            ),
            'active': url.namespace == 'plugins:exhibitors',
            'icon': 'map-pin',
        }
    ]


@receiver(nav_event_settings, dispatch_uid='exhibitors_nav')
def navbar_info(sender, request, **kwargs):
    url = resolve(request.path_info)
    if not request.user.has_event_permission(
            request.organizer, request.event, 'can_change_event_settings', request=request):
        return []
    return [{
        'label': 'Exhibitors',
        'url': reverse(
            'plugins:exhibitors:settings',
            kwargs={
                'event': request.event.slug,
                'organizer': request.organizer.slug,
            }
        ),
        'active': url.namespace == 'plugins:exhibitors',
    }]
