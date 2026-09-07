import logging
from urllib.parse import quote, urlsplit

from django.conf import settings
from django import template
from django.contrib.auth.models import AnonymousUser
from django.http import QueryDict
from django.urls import reverse

from django_scopes import scopes_disabled

from eventyay.base.meetup import is_meetup_event
from eventyay.base.models import Order, OrderPosition
from eventyay.common.urls import is_http_url
from eventyay.common.permissions import is_admin_mode_active, user_has_cfp_submissions
from eventyay.talk_rules.agenda import (
    is_agenda_visible,
    is_wip_agenda_url,
    public_speakers_list_available,
)
from eventyay.talk_rules.submission import (
    are_featured_submissions_visible,
    event_has_featured_submissions,
    show_featured_always,
)
from eventyay.agenda.views.utils import event_has_public_featured_schedule_talks

register = template.Library()
logger = logging.getLogger(__name__)


@register.simple_tag(takes_context=True)
def is_meetup(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    return is_meetup_event(event)


@register.filter
def get_feature_flag(event, feature_flag: str):
    return event.get_feature_flag(feature_flag)


@register.simple_tag(takes_context=True)
def cfp_locale_switch_url(context, locale_code):
    request = context.get('request')
    event = getattr(request, 'event', None)
    if not request or not event:
        logger.warning('cfp_locale_switch_url called without request.event')
        return ''
    if not event.organizer:
        logger.warning(
            'cfp_locale_switch_url called with event %s missing organizer',
            getattr(event, 'slug', '<unknown>'),
        )
        return ''
    base = reverse(
        'cfp:locale.set',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    query = QueryDict(mutable=True)
    query['locale'] = locale_code
    query['next'] = request.get_full_path()
    return f'{base}?{query.urlencode()}'


@register.filter
def short_user_label(user):
    """
    Compact user display: prefer first name, then full name, then email local part.
    Truncate to 11 chars with ellipsis when longer.
    """
    if not user:
        return ''
    first = getattr(user, 'first_name', None) or getattr(user, 'firstname', None)
    if not first:
        fullname = getattr(user, 'fullname', None) or getattr(user, 'name', None)
        if fullname:
            parts = fullname.split()
            first = parts[0] if parts else fullname
    email = getattr(user, 'email', '') or ''
    label = (first or '').strip() or (email.split('@')[0] if email else '')
    if len(label) > 11:
        label = label[:11] + '…'
    return label


@register.simple_tag(takes_context=True)
def user_has_valid_ticket(context, event=None):
    """Return True if the current authenticated user has a valid order/ticket granting video access.

    Mirrors the access rules used by the presale online video join flow.
    """
    request = context.get('request')
    if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
        return False

    event = event or getattr(request, 'event', None)
    if not event:
        return False

    if not request.user.email:
        return False

    allowed_statuses = [Order.STATUS_PAID]
    if event.settings.venueless_allow_pending:
        allowed_statuses.append(Order.STATUS_PENDING)

    if event.settings.venueless_all_products:
        return OrderPosition.objects.filter(
            order__event=event,
            order__email__iexact=request.user.email,
            order__status__in=allowed_statuses,
            product__admission=True,
            canceled=False,
            addon_to__isnull=True,
        ).exists()

    allowed_products = event.settings.venueless_products or []
    if not allowed_products:
        return False

    return OrderPosition.objects.filter(
        order__event=event,
        order__email__iexact=request.user.email,
        order__status__in=allowed_statuses,
        product_id__in=allowed_products,
        canceled=False,
        addon_to__isnull=True,
    ).exists()


@register.filter
def startswith(value, arg):
    """Usage: {% if value|startswith:"arg" %}"""
    if isinstance(value, str):
        return value.startswith(arg)
    return False


@register.simple_tag(takes_context=True)
def append_si(context, url: str | None, signature: str | None) -> str:
    if not url:
        return ''
    if not signature:
        return url

    if is_http_url(url):
        url_netloc = urlsplit(url).netloc.lower()
        site_netloc = urlsplit(settings.SITE_URL).netloc.lower()
        request = context.get('request')
        request_netloc = request.get_host().lower() if request else ''
        if url_netloc and url_netloc not in {site_netloc, request_netloc}:
            return url
    elif urlsplit(url).scheme:
        return url

    separator = '&' if '?' in url else '?'
    return f"{url}{separator}si={quote(str(signature))}"


@register.simple_tag(takes_context=True)
def tickets_tab_visible(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    if request and not event.user_can_view_tickets(getattr(request, 'user', None), request=request):
        return False

    target_event = context.get('ev') or context.get('subevent') or event
    if target_event and not target_event.presale_is_running and not event.settings.show_products_outside_presale_period:
        return False

    productnum = context.get('productnum')
    if productnum is not None:
        try:
            return int(productnum) != 0
        except (TypeError, ValueError):
            return bool(productnum)
    channel = getattr(getattr(request, 'sales_channel', None), 'identifier', 'web')
    with scopes_disabled():
        return event.products.filter_available(channel=channel).exists()


@register.simple_tag(takes_context=True)
def can_view_tickets(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    return event.user_can_view_tickets(getattr(request, 'user', None), request=request)


@register.simple_tag(takes_context=True)
def can_list_schedule(context, event=None):
    """Whether schedule-related navigation should be shown on public pages."""
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not request or not event:
        return False

    user = getattr(request, 'user', None) or AnonymousUser()
    if getattr(user, 'is_authenticated', False):
        if is_admin_mode_active(request):
            return True
        return user.has_perm('base.list_schedule', event)

    return bool(
        event.talks_published
        and event.get_feature_flag('show_schedule')
        and event.current_schedule
    )


@register.simple_tag(takes_context=True)
def show_public_speakers_list(context, event=None):
    """Whether the public speakers overview page and nav link may be shown."""
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not request or not event:
        return False
    return public_speakers_list_available(AnonymousUser(), event)


@register.simple_tag(takes_context=True)
def show_schedule_nav_tab(context, event=None):
    """Whether the schedule header tab should link to the public schedule."""
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not request or not event:
        return False
    if not can_list_schedule(context, event):
        return False

    path = getattr(request, 'path_info', '') or ''
    user = getattr(request, 'user', None) or AnonymousUser()

    if is_wip_agenda_url(path):
        return True
    if is_agenda_visible(user, event) and event.has_schedule_content:
        return True
    if '/featured/' in path:
        return False
    if '/schedule/' in path and '/speakers/' not in path and '/talk/' not in path:
        return True
    return False


@register.simple_tag(takes_context=True)
def can_view_talks(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    return event.user_can_view_talks(getattr(request, 'user', None), request=request)


@register.simple_tag(takes_context=True)
def can_view_featured_sessions_public(context, event=None):
    """Whether public UI may link to featured sessions (same gate as :class:`FeaturedView`).

    Uses ``are_featured_submissions_visible`` so org setting "Show featured sessions" applies
    to everyone (including organizers on the public site). ``has_perm('list_featured')`` is
    intentionally not used here: it always passes for orga via ``orga_can_change_submissions``.
    """
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not request or not event:
        return False

    user = getattr(request, 'user', None)
    if user is None:
        return False
    if not are_featured_submissions_visible(user, event):
        return False
    if show_featured_always(event):
        return True

    if event.current_schedule:
        has_featured = event_has_public_featured_schedule_talks(event)
    else:
        has_featured = event_has_featured_submissions(event)

    return has_featured


@register.simple_tag(takes_context=True)
def private_testmode_tickets_enabled(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    return event.private_testmode and event.settings.get('private_testmode_tickets', True, as_type=bool)


@register.simple_tag(takes_context=True)
def private_testmode_talks_enabled(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    return event.private_testmode and event.settings.get('private_testmode_talks', False, as_type=bool)


@register.simple_tag(takes_context=True)
def has_organizer_access(context, organizer=None):
    """Return True if the user may access organizer management for this organizer."""
    request = context.get('request')
    organizer = organizer or getattr(request, 'organizer', None)
    user = getattr(request, 'user', None)
    if not organizer or not user or not user.is_authenticated:
        return False
    if user.is_administrator:
        return True
    return user.has_organizer_permission(organizer, request=request)


@register.simple_tag(takes_context=True)
def is_event_team_member(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    user = getattr(request, 'user', None)
    if not event or not user or user.is_anonymous:
        return False
    return user.has_event_permission(event.organizer, event, request=request)


@register.simple_tag(takes_context=True)
def user_has_submissions(context, event=None):
    """Return True if the authenticated user has submitted proposals for this event."""
    request = context.get('request')
    if not request:
        return False
    user = request.user
    if not user.is_authenticated:
        return False
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    return user_has_cfp_submissions(request, event)
