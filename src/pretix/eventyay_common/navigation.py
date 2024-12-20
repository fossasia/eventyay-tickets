from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.http import HttpRequest
from pretix.control.navigation import merge_in
from pretix.control.signals import nav_global
from django.utils.translation import gettext_lazy as _

from pretix.control.signals import (
    nav_event, nav_global,
)


def get_global_navigation(request):
    url = request.resolver_match
    if not url:
        return []
    request.user.has_active_staff_session(request.session.session_key)
    nav = [
        {
            'label': _('Dashboard'),
            'url': reverse('eventyay_common:dashboard'),
            'active': (url.url_name == 'dashboard'),
            'icon': 'dashboard',
        },
        {
            'label': _('My Events'),
            'url': reverse('eventyay_common:events'),
            'active': 'events' in url.url_name,
            'icon': 'calendar',
        },
        {
            'label': _('Organizers'),
            'url': reverse('eventyay_common:organizers'),
            'active': 'organizers' in url.url_name,
            'icon': 'group',
        },
        {
            'label': _('Account'),
            'url': reverse('eventyay_common:account'),
            'active': 'account' in url.url_name,
            'icon': 'user',
        }

    ]

    merge_in(nav, sorted(
        sum((list(a[1]) for a in nav_global.send(request, request=request)), []),
        key=lambda r: (1 if r.get('parent') else 0, r['label'])
    ))
    return nav

def get_event_navigation(request: HttpRequest):
    url = request.resolver_match
    if not url:
        return []
    request.user.has_active_staff_session(request.session.session_key)
    nav = [
        {
            'label': _('Dashboard'),
            'url': reverse('eventyay_common:event.index', kwargs={
                'event': request.event.slug,
                'organizer': request.event.organizer.slug,
            }),
            'active': (url.url_name == 'event.index'),
            'icon': 'dashboard',
        },
        {
            'label': _('Settings'),
            'url': reverse('eventyay_common:event.update', kwargs={
                'event': request.event.slug,
                'organizer': request.event.organizer.slug,
            }),
            'active': (url.url_name == 'event.update'),
            'icon': 'wrench',
        }
    ]

    merge_in(nav, sorted(
        sum((list(a[1]) for a in nav_event.send(request.event, request=request)), []),
        key=lambda r: (1 if r.get('parent') else 0, r['label'])
    ))

    return nav
