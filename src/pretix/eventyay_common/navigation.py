from typing import Any, Dict, List

from django.http import HttpRequest
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from pretix.base.models import Event
from pretix.control.navigation import merge_in
from pretix.control.signals import nav_event, nav_global


def get_global_navigation(request: HttpRequest) -> List[Dict[str, Any]]:
    """Generate navigation items for global."""
    url = request.resolver_match
    if not url:
        return []
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
        },
    ]

    # Merge plugin-provided navigation items
    plugin_responses = nav_global.send(request, request=request)
    plugin_nav_items = []
    for receiver, response in plugin_responses:
        if response:
            plugin_nav_items.extend(response)

    # Sort navigation items, prioritizing non-parent items and alphabetically
    sorted_plugin_items = sorted(plugin_nav_items, key=lambda r: (1 if r.get('parent') else 0, r['label']))

    # Merge plugin items into default navigation
    merge_in(nav, sorted_plugin_items)

    return nav


def get_event_navigation(request: HttpRequest, event: Event) -> List[Dict[str, Any]]:
    """Generate navigation items for an event."""
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            'label': _('Dashboard'),
            'url': reverse(
                'eventyay_common:event.index',
                kwargs={
                    'event': event.slug,
                    'organizer': event.organizer.slug,
                },
            ),
            'active': (url.url_name == 'event.index'),
            'icon': 'dashboard',
        },
        {
            'label': _('Settings'),
            'url': reverse(
                'eventyay_common:event.update',
                kwargs={
                    'event': event.slug,
                    'organizer': event.organizer.slug,
                },
            ),
            'active': (url.url_name == 'event.update'),
            'icon': 'wrench',
        },
    ]

    # Merge plugin-provided navigation items
    plugin_responses = nav_event.send(event, request=request)
    plugin_nav_items = []
    for receiver, response in plugin_responses:
        if response:
            plugin_nav_items.extend(response)

    # Sort navigation items, prioritizing non-parent items and alphabetically
    sorted_plugin_items = sorted(plugin_nav_items, key=lambda r: (1 if r.get('parent') else 0, r['label']))

    # Merge plugin items into default navigation
    merge_in(nav, sorted_plugin_items)

    return nav
