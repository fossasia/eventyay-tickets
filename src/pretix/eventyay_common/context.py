from importlib import import_module

from django.conf import settings
from django.db.models import Q
from django.urls import Resolver404, get_script_prefix, resolve
from django_scopes import scope

from pretix.base.models.auth import StaffSession
from pretix.base.settings import GlobalSettingsObject
from pretix.eventyay_common.navigation import (
    get_event_navigation, get_global_navigation,
)

from ..multidomain.urlreverse import get_event_domain

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

    if not request.path.startswith(f'{get_script_prefix()}common'):
        return {}
    ctx = {
        'url_name': url.url_name,
        'settings': settings,
        'django_settings': settings,
        'DEBUG': settings.DEBUG,
    }
    if getattr(request, 'event', None) and hasattr(request, 'organizer') and request.user.is_authenticated:
        ctx['nav_items'] = get_event_navigation(request)
        ctx['has_domain'] = get_event_domain(request.event, fallback=True) is not None
        if not request.event.testmode:
            with scope(organizer=request.organizer):
                complain_testmode_orders = request.event.cache.get('complain_testmode_orders')
                if complain_testmode_orders is None:
                    complain_testmode_orders = request.event.orders.filter(testmode=True).exists()
                    request.event.cache.set('complain_testmode_orders', complain_testmode_orders, 30)
            ctx['complain_testmode_orders'] = complain_testmode_orders and request.user.has_event_permission(
                request.organizer, request.event, 'can_view_orders', request=request
            )
        else:
            ctx['complain_testmode_orders'] = False
        if not request.event.live and ctx['has_domain']:
            child_sess = request.session.get(f'child_session_{request.event.pk}')
            s = SessionStore()
            if not child_sess or not s.exists(child_sess):
                s[f'pretix_event_access_{request.event.pk}'] = request.session.session_key
                s.create()
                ctx['new_session'] = s.session_key
                request.session[f'child_session_{request.event.pk}'] = s.session_key
            else:
                ctx['new_session'] = child_sess
            request.session['event_access'] = True
        if request.GET.get('subevent', ''):
            # Do not use .get() for lazy evaluation
            ctx['selected_subevents'] = request.event.subevents.filter(pk=request.GET.get('subevent'))

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

    ctx['talk_hostname'] = settings.TALK_HOSTNAME

    return ctx
