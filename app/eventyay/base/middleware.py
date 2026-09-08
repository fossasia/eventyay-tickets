import os
import re
import threading
import zoneinfo
from collections import OrderedDict
from urllib.parse import urlsplit

from django.apps import apps
from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.middleware.common import CommonMiddleware
from django.urls import get_script_prefix
from django.utils import timezone, translation
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation.trans_real import (
    check_for_language,
    get_supported_language_variant,
    language_code_re,
    parse_accept_lang_header,
)

from eventyay.base.i18n import get_language_without_region
from eventyay.base.models import GlobalPluginConfig
from eventyay.base.settings import global_settings_object
from eventyay.common.urls import get_url_origin
from eventyay.multidomain.urlreverse import (
    get_event_domain,
    get_organizer_domain,
)


_supported = None

DEFAULT_LEAFLET_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'


class LocaleMiddleware(MiddlewareMixin):
    """
    This middleware sets the correct locale and timezone
    for a request.
    """

    def process_request(self, request: HttpRequest):
        ui_language = getattr(request, 'ui_language', None)
        language = ui_language or get_language_from_request(request)
        # Normally, this middleware runs *before* the event is set. However, on event frontend pages it
        # might be run a second time by eventyay.presale.EventMiddleware and in this case the event is already
        # set and can be taken into account for the decision.
        if not request.path.startswith(get_script_prefix() + 'control'):
            if not ui_language:
                if hasattr(request, 'event'):
                    if language not in request.event.settings.locales:
                        firstpart = language.split('-')[0]
                        if firstpart in request.event.settings.locales:
                            language = firstpart
                        else:
                            language = request.event.settings.locale
                            for lang in request.event.settings.locales:
                                if lang.startswith(firstpart + '-'):
                                    language = lang
                                    break
                    if '-' not in language and request.event.settings.region:
                        language += '-' + request.event.settings.region
                elif hasattr(request, 'organizer'):
                    if '-' not in language and request.organizer.settings.region:
                        language += '-' + request.organizer.settings.region
        else:
            gs = global_settings_object(request)
            if '-' not in language and gs.settings.region:
                language += '-' + gs.settings.region

        translation.activate(language)
        request.LANGUAGE_CODE = get_language_without_region()

        tzname = None
        if hasattr(request, 'event'):
            tzname = request.event.settings.timezone
        elif hasattr(request, 'organizer') and 'timezone' in request.organizer.settings._cache():
            tzname = request.organizer.settings.timezone
        elif request.user.is_authenticated:
            tzname = request.user.timezone
        if tzname:
            try:
                timezone.activate(zoneinfo.ZoneInfo(tzname))
                request.timezone = tzname
            except zoneinfo.ZoneInfoNotFoundError:
                timezone.deactivate()
                request.timezone = None
        else:
            timezone.deactivate()

    def process_response(self, request: HttpRequest, response: HttpResponse):
        language = translation.get_language()
        patch_vary_headers(response, ('Accept-Language',))
        if 'Content-Language' not in response:
            response['Content-Language'] = language
        return response


def get_language_from_user_settings(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        lang_code = request.user.locale
        if lang_code in _supported and lang_code is not None and check_for_language(lang_code):
            return lang_code


def get_language_from_cookie(request: HttpRequest) -> str:
    lang_code = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    try:
        return get_supported_language_variant(lang_code)
    except LookupError:
        pass


def get_language_from_event(request: HttpRequest) -> str:
    if hasattr(request, 'event'):
        lang_code = request.event.settings.locale
        try:
            return get_supported_language_variant(lang_code)
        except LookupError:
            pass


def get_language_from_browser(request: HttpRequest) -> str:
    accept = request.headers.get('Accept-Language', '')
    for accept_lang, unused in parse_accept_lang_header(accept):
        if accept_lang == '*':
            break

        if not language_code_re.search(accept_lang):
            continue

        try:
            return get_supported_language_variant(accept_lang)
        except LookupError:
            continue


def get_default_language():
    try:
        return get_supported_language_variant(settings.LANGUAGE_CODE)
    except LookupError:  # NOQA
        return settings.LANGUAGE_CODE


def get_language_from_request(request: HttpRequest) -> str:
    """
    Analyzes the request to find what language the user wants the system to
    show. Only languages listed in settings.LANGUAGES are taken into account.
    If the user requests a sublanguage where we have a main language, we send
    out the main language.
    """
    global _supported
    if _supported is None:
        _supported = OrderedDict(settings.LANGUAGES)

    if request.path.startswith(get_script_prefix() + 'control'):
        return (
            get_language_from_user_settings(request)
            or get_language_from_cookie(request)
            or get_language_from_browser(request)
            or get_language_from_event(request)
            or get_default_language()
        )
    else:
        return (
            get_language_from_cookie(request)
            or get_language_from_user_settings(request)
            or get_language_from_browser(request)
            or get_language_from_event(request)
            or get_default_language()
        )


def _parse_csp(header):
    h = {}
    for part in header.split(';'):
        k, v = part.strip().split(' ', 1)
        h[k.strip()] = v.split(' ')
    return h


def _render_csp(h):
    return '; '.join(k + ' ' + ' '.join(v) for k, v in h.items())


def _merge_csp(a, b):
    for k, v in a.items():
        if k in b:
            a[k] += b[k]

    for k, v in b.items():
        if k not in a:
            a[k] = b[k]


def is_event_settings_preview_request(request: HttpRequest) -> bool:
    view_name = getattr(getattr(request, 'resolver_match', None), 'view_name', None) or ''
    if view_name.endswith('event.update'):
        return True

    return '/event/' in request.path and request.path.endswith('/settings/')


def get_startpage_events(request: HttpRequest):
    view_name = getattr(getattr(request, 'resolver_match', None), 'view_name', None)
    if view_name not in ('index', 'presale:index'):
        return []

    from django.db.models import Q
    from django_scopes import scopes_disabled

    from eventyay.base.models import Event

    search_query = request.GET.get('q', '').strip()
    with scopes_disabled():
        qs = Event.objects.select_related('organizer').prefetch_related('_settings_objects').filter(live=True)
        qs = qs.filter(Q(startpage_visible=True) | Q(startpage_featured=True))
        if search_query:
            qs = qs.filter(name__icontains=search_query)

        return [event for event in qs.order_by('date_from') if not event.has_component_testmode]


def get_external_image_csp_sources(request: HttpRequest) -> list[str]:
    if is_event_settings_preview_request(request):
        sources = ['https:']
        if settings.SITE_URL.startswith('http://'):
            sources.append('http:')
        return sources

    sources = []

    event = getattr(request, 'event', None)
    if event and event.pk:
        for image_url in (event.visible_header_image_url, event.visible_logo_url):
            origin = get_url_origin(image_url)
            if origin:
                sources.append(origin)

    for event in get_startpage_events(request):
        for image_url in (event.visible_header_image_url, event.visible_logo_url):
            origin = get_url_origin(image_url)
            if origin:
                sources.append(origin)

    sources.extend(getattr(request, '_external_image_csp_sources', []))

    return list(OrderedDict.fromkeys(sources))


class SecurityMiddleware(MiddlewareMixin):
    CSP_EXEMPT = ('/api/v1/docs/',)

    @staticmethod
    def _vite_dev_csp_entries():
        """Return (http_origins, ws_origins) lists for all Vite dev servers."""
        http_origins = []
        ws_origins = []
        for url in settings.VITE_DEV_SERVER_PORTS.values():
            split = urlsplit(url)
            if not split.scheme or not split.netloc:
                continue

            http_origins.append(f'{split.scheme}://{split.netloc}')
            ws_scheme = 'wss' if split.scheme == 'https' else 'ws'
            ws_origins.append(f'{ws_scheme}://{split.netloc}')
        return http_origins, ws_origins

    def process_response(self, request, resp):
        if settings.DEBUG and resp.status_code >= 400:
            # Don't use CSP on debug error page as it breaks of Django's fancy error
            # pages
            return resp

        resp['X-XSS-Protection'] = '1'

        # We just need to have a P3P, not matter whats in there
        # https://blogs.msdn.microsoft.com/ieinternals/2013/09/17/a-quick-look-at-p3p/
        # https://github.com/pretix/pretix/issues/765
        resp['P3P'] = 'CP="ALL DSP COR CUR ADM TAI OUR IND COM NAV INT"'
        # Set Referrer-Policy for YouTube embed compatibility (fixes Error 153)
        # https://developers.google.com/youtube/terms/required-minimum-functionality#embedded-player-api-client-identity
        resp['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        img_src = []
        external_img_src = get_external_image_csp_sources(request)
        gs = global_settings_object(request)
        leaflet_tiles = gs.settings.leaflet_tiles or DEFAULT_LEAFLET_TILES
        try:
            img_src.append(leaflet_tiles[: leaflet_tiles.index('/', 10)].replace('{s}', '*'))
        except (ValueError, IndexError):
            pass

        vite_http = []
        vite_ws = []
        if settings.DEBUG or settings.VITE_DEV_MODE:
            vite_http, vite_ws = self._vite_dev_csp_entries()

        h = {
            'default-src': ['{static}'],
            'script-src': [
                '{static}',
                'https://static.cloudflareinsights.com',
                'https://challenges.cloudflare.com',
                'https://checkout.stripe.com',
                'https://js.stripe.com',
                *vite_http,
                "'unsafe-eval'",  # Required for buntpapier and other libraries that use eval()
            ],
            'object-src': ["'none'"],
            'frame-src': [
                '{static}',
                'https://challenges.cloudflare.com',
                'https://checkout.stripe.com',
                'https://js.stripe.com',
                'https://www.youtube.com',
                'https://www.youtube-nocookie.com',  # Privacy-enhanced YouTube embeds
                'https:',  # Allow all HTTPS iframes
            ],
            'style-src': [
                '{static}',
                '{media}',
                "'unsafe-inline'",  # allow inline styles
            ],
            'connect-src': [
                '{dynamic}',
                '{media}',
                'https://challenges.cloudflare.com',
                'https://checkout.stripe.com',
                'https://static.cloudflareinsights.com',
                'https:',
                'blob:',
            ],
            'img-src': [
                '{static}',
                '{media}',
                'data:',
                'https://*.stripe.com',
                'https://twemoji.maxcdn.com',
                'https://www.gravatar.com',
                'https://secure.gravatar.com',
            ]
            + external_img_src
            + img_src,
            'font-src': [
                '{static}',
                'data:',
                'https://fonts.gstatic.com',  # fix Google Fonts
                *vite_http,
            ],
            'media-src': ['{static}', 'data:', 'https:', 'blob:'],
            # form-action is not only used to match on form actions, but also on URLs
            # form-actions redirect to. In the context of e.g. payment providers or
            # single-sign-on this can be nearly anything so we cannot really restrict
            # this. However, we'll restrict it to HTTPS.
            'form-action': ['{dynamic}', 'https:'] + (['http:'] if settings.SITE_URL.startswith('http://') else []),
        }

        # Allow inline scripts ONLY for video pages (Venueless integration requires it)
        # VideoSPAView injects inline <script> tags with window.venueless configuration
        if request.path.startswith('/video/'):
            h['script-src-elem'] = [
                '{static}',
                "'unsafe-eval'",  # Required for Vue.js and buntpapier libraries
                "'unsafe-inline'",  # Required for server-injected configuration scripts
            ]
            if settings.DEBUG or settings.VITE_DEV_MODE:
                for origin in vite_http:
                    h['script-src-elem'].insert(1, origin)
        if settings.LOG_CSP:
            base_path = settings.BASE_PATH
            h['report-uri'] = [f'{base_path}/csp_report/']
        if 'Content-Security-Policy' in resp:
            _merge_csp(h, _parse_csp(resp['Content-Security-Policy']))
        if settings.CSP_ADDITIONAL_HEADER:
            _merge_csp(h, _parse_csp(settings.CSP_ADDITIONAL_HEADER))

        csp_update = getattr(resp, '_csp_update', None)
        if csp_update:
            normalized = {}
            for key, value in csp_update.items():
                if value is None or value is False:
                    continue
                if isinstance(value, str):
                    parts = [part for part in value.split() if part]
                elif isinstance(value, (list, tuple, set)):
                    parts = [str(part) for part in value if part]
                else:
                    parts = [str(value)]
                if parts:
                    normalized[key] = parts
            if normalized:
                _merge_csp(h, normalized)

        staticdomain = "'self'"
        dynamicdomain = "'self'"
        mediadomain = "'self'"
        if settings.MEDIA_URL.startswith('http'):
            mediadomain += ' ' + settings.MEDIA_URL[: settings.MEDIA_URL.find('/', 9)]
        if settings.STATIC_URL.startswith('http'):
            staticdomain += ' ' + settings.STATIC_URL[: settings.STATIC_URL.find('/', 9)]
        if settings.SITE_URL.startswith('http'):
            if settings.SITE_URL.find('/', 9) > 0:
                staticdomain += ' ' + settings.SITE_URL[: settings.SITE_URL.find('/', 9)]
                dynamicdomain += ' ' + settings.SITE_URL[: settings.SITE_URL.find('/', 9)]
            else:
                staticdomain += ' ' + settings.SITE_URL
                dynamicdomain += ' ' + settings.SITE_URL

        if hasattr(request, 'organizer') and request.organizer:
            if hasattr(request, 'event') and request.event:
                domain = get_event_domain(request.event, fallback=True)
            else:
                domain = get_organizer_domain(request.organizer)
            if domain:
                siteurlsplit = urlsplit(settings.SITE_URL)
                if siteurlsplit.port and siteurlsplit.port not in (80, 443):
                    domain = f'{domain}:{siteurlsplit.port}'
                dynamicdomain += ' ' + domain

        # Add development mode settings before rendering CSP
        if settings.DEBUG or settings.VITE_DEV_MODE:
            h.setdefault('script-src', []).extend(["'unsafe-inline'", *vite_http])
            h.setdefault('connect-src', []).extend([*vite_http, *vite_ws])

        if request.path not in self.CSP_EXEMPT and not getattr(resp, '_csp_ignore', False):
            for k, v in h.items():
                h[k] = ' '.join(v).format(static=staticdomain, dynamic=dynamicdomain, media=mediadomain).split(' ')
            resp['Content-Security-Policy'] = _render_csp(h)
        elif 'Content-Security-Policy' in resp:
            del resp['Content-Security-Policy']

        return resp


class CustomCommonMiddleware(CommonMiddleware):
    def get_full_path_with_slash(self, request):
        """
        Raise an error regardless of DEBUG mode when in POST, PUT, or PATCH.
        """
        new_path = super().get_full_path_with_slash(request)
        if request.method in ('POST', 'PUT', 'PATCH'):
            raise Http404('Please append a / at the end of the URL')
        return new_path


class GloballyDisabledPluginMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        module = getattr(view_func, '__module__', None)
        if not module:
            return None

        app_config = apps.get_containing_app_config(module)
        if app_config is None or not hasattr(app_config, 'EventyayPluginMeta'):
            return None

        if app_config.name in GlobalPluginConfig.get_disabled_modules():
            raise Http404
        return None


try:
    MAX_CONCURRENT_REQUESTS = int(os.environ.get('MAX_CONCURRENT_REQUESTS', '4'))
except ValueError:
    MAX_CONCURRENT_REQUESTS = 4

CHECKIN_EXEMPT_RE = re.compile(
    r'/checkin/redeem/?(?:$|\?)|/checkinlists(?:/\d+)?(?:/|$|\?)'
)


def request_prefers_html(request):
    accept = request.headers.get('Accept', '')
    return 'text/html' in accept and 'application/json' not in accept


def request_prefers_json_api(request):
    path = request.path or ''
    if path.startswith('/api/'):
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept and 'text/html' not in accept


def is_load_shed_exempt(path):
    if path.startswith('/healthcheck') or '/video/assets/' in path:
        return True
    return bool(CHECKIN_EXEMPT_RE.search(path))


def should_skip_session_save(response, modified):
    return response.status_code == 404 and not modified


def overloaded_response(request: HttpRequest) -> HttpResponse:
    if request_prefers_html(request) and not request.path.startswith('/api/'):
        response = HttpResponse(
            'Server is temporarily overloaded. Please try again shortly.',
            status=503,
            content_type='text/plain',
        )
    else:
        response = JsonResponse(
            {'detail': 'Server is temporarily overloaded. Please try again shortly.'},
            status=503,
        )
    response['Retry-After'] = '10'
    return response


class LoadSheddingMiddleware:
    """Per-process HTTP concurrency cap (not cluster-wide).

    Default 4 concurrent requests per Gunicorn worker process, aligned with
    ``gthread`` ``--threads 4`` in production compose. With ``workers=2`` the
    effective container cap is roughly 8. Set ``MAX_CONCURRENT_REQUESTS=0`` to
    disable. Overloaded responses include ``Retry-After`` and keep JSON for API
    callers while returning a simple 503 page to browsers.
    """

    active_requests = 0
    lock = threading.Lock()

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if MAX_CONCURRENT_REQUESTS <= 0:
            return self.get_response(request)
        if is_load_shed_exempt(request.path):
            return self.get_response(request)

        with LoadSheddingMiddleware.lock:
            if LoadSheddingMiddleware.active_requests >= MAX_CONCURRENT_REQUESTS:
                return overloaded_response(request)
            LoadSheddingMiddleware.active_requests += 1

        try:
            return self.get_response(request)
        finally:
            with LoadSheddingMiddleware.lock:
                LoadSheddingMiddleware.active_requests -= 1
