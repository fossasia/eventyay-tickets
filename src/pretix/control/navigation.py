from django.http import HttpRequest
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from pretix.control.signals import (
    nav_event,
    nav_event_settings,
    nav_global,
    nav_organizer,
)


def get_event_navigation(request: HttpRequest):
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
                'label': _('Plugins'),
                'url': reverse(
                    'control:event.settings.plugins',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.plugins',
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
                'label': _('E-mail'),
                'url': reverse(
                    'control:event.settings.mail',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.mail',
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
                'label': _('Settings'),
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
                    'control:event.items',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name in ('event.item', 'event.items.add', 'event.items')
                or 'event.item.' in url.url_name,
            },
            {
                'label': _('Quotas'),
                'url': reverse(
                    'control:event.items.quotas',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.items.quota' in url.url_name,
            },
            {
                'label': _('Categories'),
                'url': reverse(
                    'control:event.items.categories',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.items.categories' in url.url_name,
            },
            {
                'label': _('Questions'),
                'url': reverse(
                    'control:event.items.questions',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.items.questions' in url.url_name,
            },
        ]

        if 'can_view_vouchers' in request.eventpermset:
            children.extend(
                [
                    {
                        'label': _('All vouchers'),
                        'url': reverse(
                            'control:event.vouchers',
                            kwargs={
                                'event': request.event.slug,
                                'organizer': request.event.organizer.slug,
                            },
                        ),
                        'active': url.url_name != 'event.vouchers.tags' and 'event.vouchers' in url.url_name,
                    },
                    {
                        'label': _('Voucher Tags'),
                        'url': reverse(
                            'control:event.vouchers.tags',
                            kwargs={
                                'event': request.event.slug,
                                'organizer': request.event.organizer.slug,
                            },
                        ),
                        'active': 'event.vouchers.tags' in url.url_name,
                    },
                ]
            )

        nav.append(
            {
                'label': _('Products'),
                'url': reverse(
                    'control:event.items',
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

    if 'can_view_orders' in request.eventpermset:
        children = [
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
            {
                'label': _('Export'),
                'url': reverse(
                    'control:event.orders.export',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.orders.export' in url.url_name,
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
        ]
        if 'can_change_orders' in request.eventpermset:
            children.append(
                {
                    'label': _('Import'),
                    'url': reverse(
                        'control:event.orders.import',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': 'event.orders.import' in url.url_name,
                }
            )
        nav.append(
            {
                'label': _('Orders'),
                'url': reverse(
                    'control:event.orders',
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
                'children': [
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
                ],
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


def get_organizer_navigation(request):
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            'label': _('My events'),
            'url': reverse('control:organizer', kwargs={'organizer': request.organizer.slug}),
            'active': url.url_name == 'organizer',
            'icon': 'calendar',
        },
    ]
    if 'can_change_organizer_settings' in request.orgapermset:
        nav.append(
            {
                'label': _('Settings'),
                'url': reverse(
                    'control:organizer.edit',
                    kwargs={'organizer': request.organizer.slug},
                ),
                'icon': 'wrench',
                'children': [
                    {
                        'label': _('General'),
                        'url': reverse(
                            'control:organizer.edit',
                            kwargs={'organizer': request.organizer.slug},
                        ),
                        'active': url.url_name == 'organizer.edit',
                    },
                    # Temporary disabled
                    # {
                    #     'label': _('Event metadata'),
                    #     'url': reverse('control:organizer.properties', kwargs={
                    #         'organizer': request.organizer.slug
                    #     }),
                    #     'active': url.url_name.startswith('organizer.propert'),
                    # },
                    # {
                    #     'label': _('Webhooks'),
                    #     'url': reverse('control:organizer.webhooks', kwargs={
                    #         'organizer': request.organizer.slug
                    #     }),
                    #     'active': 'organizer.webhook' in url.url_name,
                    #     'icon': 'bolt',
                    # },
                    {
                        'label': _('Billing settings'),
                        'url': reverse(
                            'control:organizer.settings.billing',
                            kwargs={'organizer': request.organizer.slug},
                        ),
                        'active': url.url_name == 'organizer.settings.billing',
                    },
                ],
            }
        )
    if 'can_change_teams' in request.orgapermset:
        nav.append(
            {
                'label': _('Teams'),
                'url': reverse(
                    'control:organizer.teams',
                    kwargs={'organizer': request.organizer.slug},
                ),
                'active': 'organizer.team' in url.url_name and url.namespace == 'control',
                'icon': 'group',
            }
        )

    # if 'can_manage_gift_cards' in request.orgapermset:
    #     nav.append({
    #         'label': _('Gift cards'),
    #         'url': reverse('control:organizer.giftcards', kwargs={
    #             'organizer': request.organizer.slug
    #         }),
    #         'active': 'organizer.giftcard' in url.url_name,
    #         'icon': 'credit-card',
    #     })
    if 'can_change_organizer_settings' in request.orgapermset:
        nav.append(
            {
                'label': _('Devices'),
                'url': reverse(
                    'control:organizer.devices',
                    kwargs={'organizer': request.organizer.slug},
                ),
                'icon': 'tablet',
                'children': [
                    {
                        'label': _('Devices'),
                        'url': reverse(
                            'control:organizer.devices',
                            kwargs={'organizer': request.organizer.slug},
                        ),
                        'active': 'organizer.device' in url.url_name,
                    },
                    {
                        'label': _('Gates'),
                        'url': reverse(
                            'control:organizer.gates',
                            kwargs={'organizer': request.organizer.slug},
                        ),
                        'active': 'organizer.gate' in url.url_name,
                    },
                ],
            }
        )

    nav.append(
        {
            'label': _('Export'),
            'url': reverse(
                'control:organizer.export',
                kwargs={
                    'organizer': request.organizer.slug,
                },
            ),
            'active': 'organizer.export' in url.url_name,
            'icon': 'download',
        }
    )

    merge_in(
        nav,
        sorted(
            sum(
                (
                    list(a[1])
                    for a in nav_organizer.send(request.organizer, request=request, organizer=request.organizer)
                ),
                [],
            ),
            key=lambda r: (1 if r.get('parent') else 0, r['label']),
        ),
    )
    return nav


def merge_in(nav, newnav):
    for item in newnav:
        if 'parent' in item:
            parents = [n for n in nav if n['url'] == item['parent']]
            if parents:
                if 'children' not in parents[0]:
                    parents[0]['children'] = [dict(parents[0])]
                    parents[0]['active'] = False
                parents[0]['children'].append(item)
                continue
        nav.append(item)


def get_admin_navigation(request):
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            'label': _('Admin Dashboard'),
            'url': reverse('control:admin.dashboard'),
            'active': 'dashboard' in url.url_name,
            'icon': 'dashboard',
        },
        {
            'label': _('All Events'),
            'url': reverse('control:admin.events'),
            'active': 'events' in url.url_name,
            'icon': 'calendar',
        },
        {
            'label': _('All Organizers'),
            'url': reverse('control:admin.organizers'),
            'active': 'organizers' in url.url_name,
            'icon': 'group',
        },
        {
            'label': _('Task management'),
            'url': reverse('control:admin.task_management'),
            'active': 'task_management' in url.url_name,
            'icon': 'tasks',
        },
        {
            'label': _('Pages'),
            'url': reverse('control:admin.pages'),
            'active': 'pages' in url.url_name,
            'icon': 'file-text',
        },
        {
            'label': _('Users'),
            'url': reverse('control:admin.users'),
            'active': False,
            'icon': 'user',
            'children': [
                {
                    'label': _('All users'),
                    'url': reverse('control:admin.users'),
                    'active': ('users' in url.url_name),
                },
                {
                    'label': _('Admin sessions'),
                    'url': reverse('control:admin.user.sudo.list'),
                    'active': ('sudo' in url.url_name),
                },
            ],
        },
        {
            'label': _('Vouchers'),
            'url': reverse('control:admin.vouchers'),
            'active': 'vouchers' in url.url_name,
            'icon': 'tags',
        },
        {
            'label': _('Global settings'),
            'url': reverse('control:admin.global.settings'),
            'active': False,
            'icon': 'wrench',
            'children': [
                {
                    'label': _('Settings'),
                    'url': reverse('control:admin.global.settings'),
                    'active': (url.url_name == 'admin.global.settings'),
                },
                {
                    'label': _('Update check'),
                    'url': reverse('control:admin.global.update'),
                    'active': (url.url_name == 'admin.global.update'),
                },
                {
                    'label': _('Generate keys for SSO'),
                    'url': reverse('control:admin.global.sso'),
                    'active': (url.url_name == 'admin.global.sso'),
                },
                {
                    'label': _('Social login settings'),
                    'url': reverse('plugins:socialauth:admin.global.social.auth.settings'),
                    'active': (url.url_name == 'admin.global.social.auth.settings'),
                },
                {
                    'label': _('Billing Validation'),
                    'url': reverse('control:admin.toggle.billing.validation'),
                    'active': (url.url_name == 'admin.toggle.billing.validation'),
                },
            ],
        },
        {
            'label': _('Talk admin config'),
            'url': '/talk/orga/admin/',
            'active': False,
            'icon': 'group',
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
