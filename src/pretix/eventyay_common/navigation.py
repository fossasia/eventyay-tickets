import logging
from typing import List, TypedDict

from django.http import HttpRequest
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from pretix.base.models import Event
from pretix.control.navigation import merge_in
from pretix.control.signals import nav_event, nav_global


logger = logging.getLogger(__name__)


class MenuItem(TypedDict):
    label: str
    url: str
    active: bool
    icon: str


def get_global_navigation(request: HttpRequest) -> List[MenuItem]:
    """Generate navigation items for global."""
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            "label": _("My Orders"),
            "url": reverse("eventyay_common:orders"),
            "active": "orders" in url.url_name,
            "icon": "shopping-cart",
        },
        {
            "label": _("My Events"),
            "url": reverse("eventyay_common:events"),
            "active": "events" in url.url_name,
            "icon": "calendar",
        },
        {
            "label": _("Organizers"),
            "url": reverse("eventyay_common:organizers"),
            "active": "organizers" in url.url_name,
            "icon": "group",
        },
        {
            "label": _("Account"),
            "url": reverse("eventyay_common:account"),
            "active": "account" in url.url_name,
            "icon": "user",
        },
    ]

    # Merge plugin-provided navigation items
    plugin_responses = nav_global.send(request, request=request)
    plugin_nav_items = []
    for receiver, response in plugin_responses:
        if response:
            plugin_nav_items.extend(response)

    # Sort navigation items, prioritizing non-parent items and alphabetically
    sorted_plugin_items = sorted(
        plugin_nav_items, key=lambda r: (1 if r.get("parent") else 0, r["label"])
    )

    # Merge plugin items into default navigation
    merge_in(nav, sorted_plugin_items)

    return nav


def get_event_navigation(request: HttpRequest, event: Event) -> List[MenuItem]:
    """Generate navigation items for an event."""
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            "label": _("Settings"),
            "url": reverse(
                "eventyay_common:event.update",
                kwargs={
                    "event": event.slug,
                    "organizer": event.organizer.slug,
                },
            ),
            "active": (url.url_name == "event.update"),
            "icon": "wrench",
        },
    ]

    return nav


def get_account_navigation(request: HttpRequest) -> List[MenuItem]:
    """Generate navigation items for account."""
    resolver_match = request.resolver_match
    if not resolver_match:
        return []
    # Note that it does not include the "eventyay_common" namespace.
    matched_url_name = resolver_match.url_name
    return [
        {
            'label': _('General'),
            'url': reverse('eventyay_common:account.general'),
            'active': matched_url_name.startswith('account.general'),
            'icon': 'user',
        },
        {
            'label': _('Notifications'),
            'url': reverse('eventyay_common:account.notifications'),
            'active': matched_url_name.startswith('account.notifications'),
            'icon': 'bell',
        },
        {
            'label': _('Two-factor authentication'),
            'url': reverse('eventyay_common:account.2fa'),
            'active': matched_url_name.startswith('account.2fa'),
            'icon': 'lock',
        },
        {
            'label': _('OAuth applications'),
            'url': reverse('eventyay_common:account.oauth.authorized-apps'),
            'active': matched_url_name.startswith('account.oauth'),
            'icon': 'key',
        },
        {
            'label': _('History'),
            'url': reverse('eventyay_common:account.history'),
            'active': matched_url_name.startswith('account.history'),
            'icon': 'history',
        }
    ]
