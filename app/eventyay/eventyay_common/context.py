import logging
from urllib.parse import urljoin

from django.conf import settings
from django.db.models import Q
from django.http import HttpRequest
from django.urls import Resolver404, get_script_prefix, resolve
from django_scopes import scope

from eventyay.base.models.auth import StaffSession
from eventyay.base.settings import GlobalSettingsObject
from eventyay.eventyay_common.navigation import (
    get_event_navigation,
    get_global_navigation,
)

from ..helpers.plugin_enable import is_video_enabled
from ..multidomain.urlreverse import get_event_domain
from .views.event import EventCreatedFor


logger = logging.getLogger(__name__)


def contextprocessor(request: HttpRequest):
    if not hasattr(request, '_eventyay_common_default_context'):
        request._eventyay_common_default_context = _default_context(request)
    return request._eventyay_common_default_context


def _default_context(request: HttpRequest):
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
        'talk_hostname': settings.TALK_HOSTNAME,
    }

    gs = GlobalSettingsObject()
    ctx['global_settings'] = gs.settings

    if not request.user.is_authenticated:
        return ctx

    ctx['nav_items'] = get_global_navigation(request)
    ctx['staff_session'] = request.user.has_active_staff_session(request.session.session_key)
    ctx['staff_need_to_explain'] = (
        StaffSession.objects.filter(user=request.user, date_end__isnull=False).filter(
            Q(comment__isnull=True) | Q(comment='')
        )
        if request.user.is_staff and settings.PRETIX_ADMIN_AUDIT_COMMENTS
        else StaffSession.objects.none()
    )

    # Verify if the request includes an event
    event = getattr(request, 'event', None)
    if not event:
        return ctx

    ctx['talk_edit_url'] = urljoin(settings.TALK_HOSTNAME, f'orga/event/{event.slug}')
    ctx['is_video_enabled'] = is_video_enabled(event)
    ctx['is_talk_event_created'] = False
    if event.settings.create_for == EventCreatedFor.BOTH.value or event.settings.talk_schedule_public is not None:
        ctx['is_talk_event_created'] = True

    # Verify if the request includes an organizer
    organizer = getattr(request, 'organizer', None)
    if not organizer:
        return ctx

    ctx['nav_items'] = get_event_navigation(request, event)
    ctx['has_domain'] = get_event_domain(event, fallback=True) is not None
    if not event.testmode:
        with scope(organizer=organizer):
            complain_testmode_orders = event.cache.get('complain_testmode_orders')
            if complain_testmode_orders is None:
                complain_testmode_orders = event.orders.filter(testmode=True).exists()
                event.cache.set('complain_testmode_orders', complain_testmode_orders, 30)
        ctx['complain_testmode_orders'] = complain_testmode_orders and request.user.has_event_permission(
            organizer, event, 'can_view_orders', request=request
        )
    else:
        ctx['complain_testmode_orders'] = False

    if not event.live and ctx['has_domain']:
        child_sess_key = f'child_session_{event.pk}'
        child_sess = request.session.get(child_sess_key)

        if not child_sess:
            request.session[child_sess_key] = request.session.session_key
        else:
            ctx['new_session'] = child_sess
        request.session['event_access'] = True

    if request.GET.get('subevent', ''):
        subevent_id = request.GET.get('subevent', '').strip()
        try:
            pk = int(subevent_id)
            # Do not use .get() for lazy evaluation
            ctx['selected_subevents'] = event.subevents.filter(pk=pk)
        except ValueError as e:
            logger.error('Error parsing subevent ID: %s', e)

    return ctx
