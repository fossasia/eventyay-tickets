from importlib import import_module

from django.conf import settings
from django.db.models import Q
from django.urls import Resolver404, get_script_prefix, resolve, reverse
from django.utils.translation import gettext_lazy as _

from pretix.base.models.auth import StaffSession
from pretix.base.settings import GlobalSettingsObject
from pretix.control.navigation import merge_in
from pretix.control.signals import nav_global

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


def contextprocessor(request):
    """
    Adds data to all template contexts
    """
    if not hasattr(request, '_eventyay_common_default_context'):
        request._eventyay_common_default_context = _default_context(request)
    return request._eventyay_common_default_context


def _default_context(request):
    try:
        url = resolve(request.path_info)
    except Resolver404:
        return {}

    if not request.path.startswith(get_script_prefix() + 'common'):
        return {}
    ctx = {
        'url_name': url.url_name,
        'settings': settings,
        'django_settings': settings,
        'DEBUG': settings.DEBUG,
    }
    if getattr(request, 'event', None) and hasattr(request, 'organizer') and request.user.is_authenticated:
        ctx['nav_items'] = get_global_navigation(request)

    elif request.user.is_authenticated:
        ctx['nav_items'] = get_global_navigation(request)

    gs = GlobalSettingsObject()
    ctx['global_settings'] = gs.settings

    if request.user.is_authenticated:
        ctx['staff_session'] = request.user.has_active_staff_session(request.session.session_key)
        ctx['staff_need_to_explain'] = (
            StaffSession.objects.filter(user=request.user, date_end__isnull=False).filter(
                Q(comment__isnull=True) | Q(comment="")
            )
            if request.user.is_staff and settings.PRETIX_ADMIN_AUDIT_COMMENTS else StaffSession.objects.none()
        )

    return ctx


def get_global_navigation(request):
    url = request.resolver_match
    if not url:
        return []
    has_staff_session = request.user.has_active_staff_session(request.session.session_key)
    nav = [
        {
            'label': _('Dashboard'),
            'url': reverse('eventyay_common:dashboard'),
            'active': (url.url_name == 'dashboard'),
            'icon': 'dashboard',
        },
        {
            'label': _('Events'),
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
    ]

    if has_staff_session:
        nav.append({
            'label': _('Pages'),
            'url': reverse('control:global.settings'),
            'active': False,
            'icon': "file-text",
            'children': [
                {
                    'label': _('FAQ'),
                    'url': reverse('eventyay_common:pages.create'),
                    'active': (url.url_name == 'pages.create'),
                },
                {
                    'label': _('Pricing'),
                    'url': reverse('control:global.update'),
                    'active': (url.url_name == 'global.update'),
                },
                {
                    'label': _('Privacy'),
                    'url': reverse('control:global.update'),
                    'active': (url.url_name == 'global.update'),
                },
                {
                    'label': _('Terms'),
                    'url': reverse('control:global.update'),
                    'active': (url.url_name == 'global.update'),
                },
            ]
        })

    merge_in(nav, sorted(
        sum((list(a[1]) for a in nav_global.send(request, request=request)), []),
        key=lambda r: (1 if r.get('parent') else 0, r['label'])
    ))
    return nav
