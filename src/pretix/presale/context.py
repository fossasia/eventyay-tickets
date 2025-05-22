import logging

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import translation
from django.utils.translation import get_language_info
from django_scopes import get_scope
from i18nfield.strings import LazyI18nString

from pretix.base.models.page import Page
from pretix.base.settings import GlobalSettingsObject
from pretix.helpers.i18n import (
    get_javascript_format_without_seconds,
    get_moment_locale,
)

from ..base.i18n import get_language_without_region
from .signals import (
    footer_link,
    global_footer_link,
    global_html_footer,
    global_html_head,
    global_html_page_header,
    html_footer,
    html_head,
    html_page_header,
)

logger = logging.getLogger(__name__)


def contextprocessor(request):
    """
    Adds data to all template contexts
    """
    if not hasattr(request, '_pretix_presale_default_context'):
        request._pretix_presale_default_context = _default_context(request)
    return request._pretix_presale_default_context


def _default_context(request):
    if request.path.startswith('/control'):
        return {}

    ctx = {
        'css_file': None,
        'DEBUG': settings.DEBUG,
    }
    _html_head = []
    _html_page_header = []
    _html_foot = []
    _footer = []

    if hasattr(request, 'event'):
        pretix_settings = request.event.settings
    elif hasattr(request, 'organizer'):
        pretix_settings = request.organizer.settings
    else:
        pretix_settings = GlobalSettingsObject().settings

    text = pretix_settings.get('footer_text', as_type=LazyI18nString)
    link = pretix_settings.get('footer_link', as_type=LazyI18nString)

    if text:
        if link:
            _footer.append({'url': str(link), 'label': str(text)})
        else:
            ctx['footer_text'] = str(text)

    for receiver, response in global_html_page_header.send(None, request=request):
        _html_page_header.append(response)
    for receiver, response in global_html_head.send(None, request=request):
        _html_head.append(response)
    for receiver, response in global_html_footer.send(None, request=request):
        _html_foot.append(response)
    for receiver, response in global_footer_link.send(None, request=request):
        if isinstance(response, list):
            _footer += response
        else:
            _footer.append(response)

    if hasattr(request, 'event') and get_scope():
        for receiver, response in html_head.send(request.event, request=request):
            _html_head.append(response)
        for receiver, response in html_page_header.send(request.event, request=request):
            _html_page_header.append(response)
        for receiver, response in html_footer.send(request.event, request=request):
            _html_foot.append(response)
        for receiver, response in footer_link.send(request.event, request=request):
            if isinstance(response, list):
                _footer += response
            else:
                _footer.append(response)

        if request.event.settings.presale_css_file:
            ctx['css_file'] = default_storage.url(request.event.settings.presale_css_file)

        # FIXME: We should avoid hardcoding truncate length here.
        # It is not flexible because it requires the media folder to be at "/data/media/".
        ctx['event_logo'] = request.event.settings.get('logo_image', as_type=str, default='')[7:]
        try:
            ctx['social_image'] = request.event.cache.get_or_set('social_image_url', request.event.social_image, 60)
        except (ValueError, OSError) as e:
            logger.error('Could not generate social image. Error: %s', e)

        ctx['event'] = request.event
        ctx['languages'] = [get_language_info(code) for code in request.event.settings.locales]

        if request.resolver_match:
            ctx['cart_namespace'] = request.resolver_match.kwargs.get('cart_namespace', '')
    elif hasattr(request, 'organizer'):
        ctx['languages'] = [get_language_info(code) for code in request.organizer.settings.locales]

    if hasattr(request, 'organizer'):
        if request.organizer.settings.presale_css_file and not hasattr(request, 'event'):
            ctx['css_file'] = default_storage.url(request.organizer.settings.presale_css_file)
        ctx['organizer_logo'] = request.organizer.settings.get('organizer_logo_image', as_type=str, default='')[7:]
        ctx['organizer_homepage_text'] = request.organizer.settings.get(
            'organizer_homepage_text', as_type=LazyI18nString
        )
        ctx['organizer'] = request.organizer

    ctx['base_path'] = settings.BASE_PATH

    ctx['html_head'] = ''.join(h for h in _html_head if h)
    ctx['html_foot'] = ''.join(h for h in _html_foot if h)
    ctx['html_page_header'] = ''.join(h for h in _html_page_header if h)
    ctx['footer'] = _footer
    ctx['site_url'] = settings.SITE_URL

    ctx['js_datetime_format'] = get_javascript_format_without_seconds('DATETIME_INPUT_FORMATS')
    ctx['js_date_format'] = get_javascript_format_without_seconds('DATE_INPUT_FORMATS')
    ctx['js_time_format'] = get_javascript_format_without_seconds('TIME_INPUT_FORMATS')
    ctx['js_locale'] = get_moment_locale()
    ctx['html_locale'] = translation.get_language_info(get_language_without_region()).get(
        'public_code', translation.get_language()
    )
    ctx['settings'] = pretix_settings
    ctx['django_settings'] = settings

    # Check to show organizer area
    ctx['show_organizer_area'] = False
    if (
        request.user
        and request.user.is_authenticated
        and hasattr(request, 'organizer')
        and request.organizer
        and hasattr(request, 'event')
        and request.event
    ):
        ctx['show_organizer_area'] = request.user.has_event_permission(
            request.organizer,
            request.event,
            'can_change_event_settings',
            request=request,
        )

    ctx['show_link_in_header_for_all_pages'] = Page.objects.filter(link_in_header=True)
    ctx['show_link_in_footer_for_all_pages'] = Page.objects.filter(link_in_footer=True)

    return ctx
