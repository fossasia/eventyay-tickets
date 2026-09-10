from django.http import HttpRequest
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from eventyay.base.meetup import is_meetup_event
from eventyay.control.signals import (
    nav_event,
    nav_event_settings,
    nav_global,
    nav_organizer,
)


def _vouchers_nav_active(url) -> bool:
    return 'event.vouchers' in url.url_name or 'event.voucher' in url.url_name


def _vouchers_nav_item(request, url) -> dict:
    return {
        'label': _('Vouchers'),
        'url': reverse(
            'control:event.vouchers',
            kwargs={
                'event': request.event.slug,
                'organizer': request.event.organizer.slug,
            },
        ),
        'active': _vouchers_nav_active(url),
    }


def get_meetup_event_navigation(request: HttpRequest):
    url = request.resolver_match
    if not url:
        return []
    nav = []
    event = request.event
    has_settings_perm = 'can_change_event_settings' in request.eventpermset
    has_items_perm = 'can_change_items' in request.eventpermset
    has_orders_perm = 'can_view_orders' in request.eventpermset
    has_mail_perm = 'can_change_orders' in request.eventpermset

    if has_settings_perm:
        nav.append(
            {
                'label': _('Meetup settings'),
                'url': reverse(
                    'eventyay_common:event.update',
                    kwargs={
                        'event': event.slug,
                        'organizer': event.organizer.slug,
                    },
                ),
                'active': (url.url_name == 'event.update'),
                'icon': 'wrench',
            }
        )

    if has_orders_perm:
        nav.append(
            {
                'label': _('Registrations'),
                'url': reverse(
                    'control:event.orders',
                    kwargs={
                        'event': event.slug,
                        'organizer': event.organizer.slug,
                    },
                ),
                'active': url.url_name in ('event.orders', 'event.order', 'event.orders.search')
                or 'event.order.' in url.url_name,
                'icon': 'list-alt',
            }
        )

    if has_items_perm:
        nav.append(
            {
                'label': _('Products'),
                'url': reverse(
                    'control:event.products',
                    kwargs={
                        'event': event.slug,
                        'organizer': event.organizer.slug,
                    },
                ),
                'active': url.url_name in ('event.product', 'event.products.add', 'event.products')
                or 'event.product.' in url.url_name,
                'icon': 'ticket',
            }
        )
        nav.append(
            {
                'label': _('Quotas'),
                'url': reverse(
                    'control:event.products.quotas',
                    kwargs={
                        'event': event.slug,
                        'organizer': event.organizer.slug,
                    },
                ),
                'active': 'event.products.quota' in url.url_name,
                'icon': 'tasks',
            }
        )

    if has_settings_perm:
        nav.append(
            {
                'label': _('Payment'),
                'url': reverse(
                    'control:event.settings.payment',
                    kwargs={
                        'event': event.slug,
                        'organizer': event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.payment',
                'icon': 'credit-card',
            }
        )

    if 'eventyay.plugins.sendmail' in event.get_plugins() and has_mail_perm:
        nav.append(
            {
                'label': _('Message center'),
                'url': reverse(
                    'control:event.mail.compose',
                    kwargs={
                        'event': event.slug,
                        'organizer': event.organizer.slug,
                    },
                ),
                'active': 'event.mail' in url.url_name,
                'icon': 'envelope',
            }
        )

    return nav


def get_event_navigation(request: HttpRequest):
    if is_meetup_event(request.event):
        return get_meetup_event_navigation(request)

    url = request.resolver_match
    if not url:
        return []
    nav = []
    if 'can_change_event_settings' in request.eventpermset:
        event_settings = [
            {
                'label': _('General'),
                'url': reverse(
                    'control:event.settings',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings',
            },
            {
                'label': _('Payment'),
                'url': reverse(
                    'control:event.settings.payment',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.payment',
            },
            {
                'label': _('Tickets'),
                'url': reverse(
                    'control:event.settings.tickets',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.tickets',
            },
            {
                'label': _('Tax rules'),
                'url': reverse(
                    'control:event.settings.tax',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name.startswith('event.settings.tax'),
            },
            {
                'label': _('Invoicing'),
                'url': reverse(
                    'control:event.settings.invoice',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.invoice',
            },
            {
                'label': pgettext_lazy('action', 'Cancellation'),
                'url': reverse(
                    'control:event.settings.cancel',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.cancel',
            },
            {
                'label': _('Widget'),
                'url': reverse(
                    'control:event.settings.widget',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.widget',
            },
        ]
        event_settings += sorted(
            sum(
                (list(a[1]) for a in nav_event_settings.send(request.event, request=request)),
                [],
            ),
            key=lambda r: r['label'],
        )
        nav.append(
            {
                'label': _('Ticket settings'),
                'url': reverse(
                    'control:event.settings',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': False,
                'icon': 'wrench',
                'children': event_settings,
            }
        )
        if request.event.has_subevents:
            nav.append(
                {
                    'label': pgettext_lazy('subevent', 'Dates'),
                    'url': reverse(
                        'control:event.subevents',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': ('event.subevent' in url.url_name),
                    'icon': 'calendar',
                }
            )

    if 'can_change_items' in request.eventpermset:
        children = [
            {
                'label': _('Products'),
                'url': reverse(
                    'control:event.products',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name in ('event.product', 'event.products.add', 'event.products')
                or 'event.product.' in url.url_name,
            },
            {
                'label': _('Quotas'),
                'url': reverse(
                    'control:event.products.quotas',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.products.quota' in url.url_name,
            },
            {
                'label': _('Categories'),
                'url': reverse(
                    'control:event.products.categories',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.products.categories' in url.url_name,
            },
            {
                'label': _('Order forms'),
                'url': reverse(
                    'control:event.products.orderforms',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.products.orderforms' in url.url_name,
            },
        ]

        if 'can_view_vouchers' in request.eventpermset:
            children.append(_vouchers_nav_item(request, url))

        nav.append(
            {
                'label': _('Products'),
                'url': reverse(
                    'control:event.products',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': False,
                'icon': 'ticket',
                'children': children,
            }
        )
    elif 'can_view_vouchers' in request.eventpermset:
        nav.append(
            {
                **_vouchers_nav_item(request, url),
                'icon': 'ticket',
            }
        )

    children = []
    if 'can_view_orders' in request.eventpermset:
        children.extend(
            [
                {
                    'label': _('Overview'),
                    'url': reverse(
                        'control:event.orders.overview',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': 'event.orders.overview' in url.url_name,
                },
                {
                    'label': _('All orders'),
                    'url': reverse(
                        'control:event.orders',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': url.url_name in ('event.orders', 'event.order', 'event.orders.search')
                    or 'event.order.' in url.url_name,
                },
                {
                    'label': _('Waiting list'),
                    'url': reverse(
                        'control:event.orders.waitinglist',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': 'event.orders.waitinglist' in url.url_name,
                },
                {
                    'label': _('Refunds'),
                    'url': reverse(
                        'control:event.orders.refunds',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': 'event.orders.refunds' in url.url_name,
                },
            ]
        )

    has_banktransfer = (
        'eventyay.plugins.banktransfer' in request.event.get_plugins()
        and 'can_manage_bank_transfers' in request.eventpermset
    )
    if 'can_view_orders' in request.eventpermset or 'can_change_orders' in request.eventpermset or has_banktransfer:
        children.append(
            {
                'label': _('Import / Export'),
                'url': reverse(
                    'control:event.orders.import_export',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': (
                    'event.orders.import_export' in url.url_name
                    or 'event.orders.export' in url.url_name
                    or 'event.orders.import' in url.url_name
                    or (url.namespace == 'plugins:banktransfer' and url.url_name in ('import', 'refunds.list', 'import.job'))
                ),
            }
        )

    if children:
        parent_url = children[0]['url']
        if 'can_view_orders' in request.eventpermset:
            parent_url = reverse(
                'control:event.orders',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.event.organizer.slug,
                },
            )
        nav.append(
            {
                'label': _('Orders'),
                'url': reverse(
                    'control:event.orders.overview',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': False,
                'icon': 'shopping-cart',
                'children': children,
            }
        )

    if 'can_view_orders' in request.eventpermset:
        checkin_children = [
            {
                'label': _('Check-in lists'),
                'url': reverse(
                    'control:event.orders.checkinlists',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.orders.checkin' in url.url_name,
            },
        ]
        nav.append(
            {
                'label': pgettext_lazy('navigation', 'Check-in'),
                'url': reverse(
                    'control:event.orders.checkinlists',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': False,
                'icon': 'check-square-o',
                'children': checkin_children,
            }
        )

    merge_in(
        nav,
        sorted(
            sum((list(a[1]) for a in nav_event.send(request.event, request=request)), []),
            key=lambda r: (1 if r.get('parent') else 0, r['label']),
        ),
    )

    return nav


def get_global_navigation(request):
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            'label': _('My events'),
            'url': reverse('eventyay_common:events'),
            'active': 'events' in url.url_name,
            'icon': 'calendar',
        },
        {
            'label': _('Organizers'),
            'url': reverse('control:organizers'),
            'active': 'organizers' in url.url_name,
            'icon': 'group',
        },
        {
            'label': _('Order search'),
            'url': reverse('control:search.orders'),
            'active': 'search.orders' in url.url_name,
            'icon': 'search',
        },
    ]

    merge_in(
        nav,
        sorted(
            sum((list(a[1]) for a in nav_global.send(request, request=request)), []),
            key=lambda r: (1 if r.get('parent') else 0, r['label']),
        ),
    )
    return nav


def merge_in(nav, newnav):
    for product in newnav:
        if 'parent' in product:
            parents = [n for n in nav if n['url'] == product['parent']]
            if parents:
                if 'children' not in parents[0]:
                    parents[0]['children'] = [dict(parents[0])]
                    parents[0]['active'] = False
                parents[0]['children'].append(product)
                continue
        nav.append(product)


def get_admin_navigation(request):
    url = request.resolver_match
    if not url:
        return []
    business_children = [
        {
            'label': _('Business Settings'),
            'url': reverse('eventyay_admin:admin.global.business'),
            'active': (url.url_name == 'admin.global.business'),
        },
        {
            'label': _('Event vouchers'),
            'url': reverse('eventyay_admin:admin.vouchers'),
            'active': 'voucher' in url.url_name,
        },
    ]

    global_settings_children = [
        {
            'label': _('Settings'),
            'url': reverse('eventyay_admin:admin.global.settings'),
            'active': (url.url_name == 'admin.global.settings'),
        },
        {
            'label': _('Ticketing'),
            'url': reverse('eventyay_admin:admin.global.ticketing'),
            'active': (url.url_name == 'admin.global.ticketing'),
        },
        {
            'label': _('System information'),
            'url': reverse('eventyay_admin:admin.config'),
            'active': 'config' in url.url_name,
        },
        {
            'label': _('Pages'),
            'url': reverse('eventyay_admin:admin.pages'),
            'active': 'pages' in url.url_name,
        },
        {
            'label': _('Generate keys for SSO'),
            'url': reverse('eventyay_admin:admin.global.sso'),
            'active': (url.url_name == 'admin.global.sso'),
        },
        {
            'label': _('Social login settings'),
            'url': reverse('plugins:socialauth:admin.global.social.auth.settings'),
            'active': (url.url_name == 'admin.global.social.auth.settings'),
        },
        {
            'label': _('Plugins'),
            'url': reverse('eventyay_admin:admin.global.plugins'),
            'active': (url.url_name == 'admin.global.plugins'),
        },
    ]
    nav = [
        {
            'label': _('Global settings'),
            'url': reverse('eventyay_admin:admin.global.settings'),
            'active': any(c['active'] for c in global_settings_children),
            'icon': 'wrench',
            'children': global_settings_children,
        },
        {
            'label': _('Business'),
            'url': reverse('eventyay_admin:admin.global.business'),
            'active': any(c['active'] for c in business_children),
            'icon': 'briefcase',
            'children': business_children,
        },
        {
            'label': _('Task management'),
            'url': reverse('eventyay_admin:admin.task_management'),
            'active': 'task_management' in url.url_name,
            'icon': 'tasks',
        },
    ]

    # --- Inject Video navigation (now part of admin sidebar) ------------------
    user = request.user
    if user.is_authenticated and user.is_staff:
        is_video_route = 'video_admin' in url.namespaces
        video_children = [
            {
                'label': _('Video settings'),
                'url': reverse('eventyay_admin:video_admin:settings'),
                'active': is_video_route and (
                    url.url_name == 'settings' or
                    url.url_name.startswith('bbbserver.') or
                    url.url_name.startswith('janusserver.') or
                    url.url_name.startswith('jitsiserver.') or
                    url.url_name.startswith('turnserver.') or
                    url.url_name.startswith('streamingserver.') or
                    url.url_name == 'server.toggle-active'
                ),
            },
            {
                'label': _('Events'),
                'url': reverse('eventyay_admin:video_admin:event.list'),
                'active': is_video_route and url.url_name.startswith('event.'),
            },
            {
                'label': _('System log'),
                'url': reverse('eventyay_admin:video_admin:systemlog.list'),
                'active': is_video_route and url.url_name.startswith('systemlog.'),
            },
        ]
        parent_active = any(c['active'] for c in video_children)
        nav.append(
            {
                'label': _('Video'),
                'url': reverse('eventyay_admin:video_admin:settings'),
                'active': parent_active,
                'icon': 'video-camera',
                'children': video_children,
            }
        )
    # --------------------------------------------------------------------------

    platform_data_children = [
        {
            'label': _('Events'),
            'url': reverse('eventyay_admin:admin.events'),
            'active': 'events' in url.url_name,
        },
        {
            'label': _('Organizers'),
            'url': reverse('eventyay_admin:admin.organizers'),
            'active': 'organizers' in url.url_name,
        },
        {
            'label': _('Attendees'),
            'url': reverse('eventyay_admin:admin.attendees'),
            'active': 'attendees' in url.url_name,
        },
        {
            'label': _('Sessions'),
            'url': reverse('eventyay_admin:admin.submissions'),
            'active': 'submissions' in url.url_name,
        },
        {
            'label': _('Orders'),
            'url': reverse('eventyay_admin:admin.orders'),
            'active': 'orders' in url.url_name,
        },
    ]

    nav.extend(
        [
            {
                'label': _('Platform Data'),
                'url': reverse('eventyay_admin:admin.events'),
                'active': any(c['active'] for c in platform_data_children),
                'icon': 'database',
                'children': platform_data_children,
            },
            {
                'label': _('Users'),
                'url': reverse('eventyay_admin:admin.users'),
                'active': False,
                'icon': 'user',
                'children': [
                    {
                        'label': _('All users'),
                        'url': reverse('eventyay_admin:admin.users'),
                        'active': ('users' in url.url_name),
                    },
                    {
                        'label': _('Admin sessions'),
                        'url': reverse('eventyay_admin:admin.user.sudo.list'),
                        'active': ('sudo' in url.url_name),
                    },
                ],
            },
        ]
    )

    merge_in(
        nav,
        sorted(
            sum((list(a[1]) for a in nav_global.send(request, request=request)), []),
            key=lambda r: (1 if r.get('parent') else 0, r['label']),
        ),
    )
    return nav
