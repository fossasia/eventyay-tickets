from contextlib import suppress
from urllib.parse import quote, urljoin

import pytz
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, reverse
from django.urls import resolve
from django.utils import timezone, translation
from django.utils.translation.trans_real import (
    get_supported_language_variant, language_code_re, parse_accept_lang_header,
)

from pretalx.event.models import Event, Organiser, Team


class EventPermissionMiddleware:
    UNAUTHENTICATED_ORGA_URLS = ('invitation.view', 'auth', 'login')

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _set_orga_events(request):
        request.is_orga = False
        request.is_reviewer = False
        request.orga_events = []
        if not request.user.is_anonymous:
            if request.user.is_administrator:
                request.orga_events = Event.objects.order_by('date_from')
                request.is_orga = True
                request.is_reviewer = True
            else:
                request.orga_events = request.user.get_events_for_permission().order_by(
                    'date_from'
                )
                if hasattr(request, 'event'):
                    request.is_orga = request.event in request.orga_events
                    request.is_reviewer = (
                        request.event
                        in request.user.get_events_for_permission(is_reviewer=True)
                    )

    def _handle_orga_url(self, request, url):
        if request.uses_custom_domain:
            return urljoin(settings.SITE_URL, request.get_full_path())
        if (
            request.user.is_anonymous
            and url.url_name not in self.UNAUTHENTICATED_ORGA_URLS
        ):
            params = '&' + request.GET.urlencode() if request.GET else ''
            return reverse('orga:login') + f'?next={quote(request.path)}' + params
        return None

    def __call__(self, request):
        url = resolve(request.path_info)

        organiser_slug = url.kwargs.get('organiser')
        if organiser_slug:
            request.organiser = get_object_or_404(
                Organiser, slug__iexact=organiser_slug
            )
            if hasattr(request, 'organiser') and request.organiser:
                request.is_orga = False
                if not request.user.is_anonymous:
                    has_perms = Team.objects.filter(
                        organiser=request.organiser,
                        members__in=[request.user],
                        can_change_organiser_settings=True,
                    ).exists()
                    request.is_orga = request.user.is_administrator or has_perms

        event_slug = url.kwargs.get('event')
        if event_slug:
            request.event = get_object_or_404(Event, slug__iexact=event_slug)

        self._set_orga_events(request)
        self._select_locale(request)

        if 'orga' in url.namespaces or (
            'plugins' in url.namespaces and request.path.startswith('/orga')
        ):
            url = self._handle_orga_url(request, url)
            if url:
                return redirect(url)
        elif (
            getattr(request, 'event', None)
            and request.event.settings.custom_domain
            and not request.uses_custom_domain
            and not ('agenda' in url.namespaces and url.url_name == 'export')
        ):
            return redirect(
                urljoin(request.event.settings.custom_domain, request.get_full_path())
            )
        return self.get_response(request)

    def _select_locale(self, request):
        supported = (
            request.event.locales
            if (hasattr(request, 'event') and request.event)
            else settings.LANGUAGES
        )
        language = (
            self._language_from_user(request, supported)
            or self._language_from_cookie(request, supported)
            or self._language_from_browser(request, supported)
        )
        if hasattr(request, 'event') and request.event:
            language = language or request.event.locale

        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

        with suppress(pytz.UnknownTimeZoneError):
            if hasattr(request, 'event') and request.event:
                tzname = request.event.timezone
            elif request.user.is_authenticated:
                tzname = request.user.timezone
            else:
                tzname = settings.TIME_ZONE
            timezone.activate(pytz.timezone(tzname))
            request.timezone = tzname

    @staticmethod
    def _language_from_browser(request, supported):
        accept_value = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        for accept_lang, _ in parse_accept_lang_header(accept_value):
            if accept_lang == '*':
                break

            if not language_code_re.search(accept_lang):
                continue

            try:
                val = get_supported_language_variant(accept_lang)
                if val and val in supported:
                    return val
            except LookupError:
                continue
        return None

    @staticmethod
    def _language_from_cookie(request, supported):
        cookie_value = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        with suppress(LookupError):
            cookie_value = get_supported_language_variant(cookie_value)
            if cookie_value and cookie_value in supported:
                return cookie_value
        return None

    @staticmethod
    def _language_from_user(request, supported):
        if request.user.is_authenticated:
            with suppress(LookupError):
                value = get_supported_language_variant(request.user.locale)
                if value and value in supported:
                    return value
