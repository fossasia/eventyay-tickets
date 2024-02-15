import zoneinfo
from contextlib import suppress
from urllib.parse import quote, urljoin

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, reverse
from django.urls import resolve
from django.utils import timezone, translation
from django.utils.translation.trans_real import (
    get_supported_language_variant,
    language_code_re,
    parse_accept_lang_header,
)
from django_scopes import scope, scopes_disabled

from pretalx.event.models import Event, Organiser, Team


def get_login_redirect(request):
    params = request.GET.copy()
    next_url = params.pop("next", None)
    next_url = next_url[0] if next_url else request.path
    params = request.GET.urlencode() if request.GET else ""
    params = f"?next={quote(next_url)}&{params}"
    event = getattr(request, "event", None)
    if event:
        url = (
            event.orga_urls.login
            if request.path.startswith("/orga")
            else event.urls.login
        )
        return redirect(url.full() + params)
    return redirect(reverse("orga:login") + params)


class EventPermissionMiddleware:
    UNAUTHENTICATED_ORGA_URLS = (
        "invitation.view",
        "auth",
        "login",
        "auth.reset",
        "auth.recover",
        "event.login",
        "event.auth.reset",
        "event.auth.recover",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _set_orga_events(request):
        request.is_orga = False
        request.orga_events = []
        if not request.user.is_anonymous:
            if request.user.is_administrator:
                request.orga_events = Event.objects.order_by("date_from")
                request.is_orga = True
            else:
                request.orga_events = request.user.get_events_for_permission().order_by(
                    "date_from"
                )
                event = getattr(request, "event", None)
                if event:
                    request.is_orga = event in request.orga_events
                    request.is_reviewer = event.teams.filter(
                        members__in=[request.user], is_reviewer=True
                    ).exists()
                    request.user.team_permissions[event.slug] = (
                        request.user.get_permissions_for_event(event)
                    )

    def _handle_orga_url(self, request, url):
        if request.uses_custom_domain:
            return redirect(urljoin(settings.SITE_URL, request.get_full_path()))
        if (
            request.user.is_anonymous
            and url.url_name not in self.UNAUTHENTICATED_ORGA_URLS
        ):
            return get_login_redirect(request)
        return None

    def __call__(self, request):
        url = resolve(request.path_info)

        organiser_slug = url.kwargs.get("organiser")
        if organiser_slug:
            request.organiser = get_object_or_404(
                Organiser, slug__iexact=organiser_slug
            )
            has_perms = (
                Team.objects.filter(
                    organiser=request.organiser,
                    members__in=[request.user],
                    can_change_organiser_settings=True,
                ).exists()
                if not request.user.is_anonymous
                else False
            )
            request.is_orga = (
                getattr(request.user, "is_administrator", False) or has_perms
            )

        event_slug = url.kwargs.get("event")
        if event_slug:
            with scopes_disabled():
                request.event = get_object_or_404(
                    Event.objects.prefetch_related("schedules", "submissions"),
                    slug__iexact=event_slug,
                )
        event = getattr(request, "event", None)

        self._set_orga_events(request)
        self._select_locale(request)
        is_exempt = (
            url.url_name == "export"
            if "agenda" in url.namespaces
            else request.path.startswith("/api/")
        )

        if "orga" in url.namespaces or (
            "plugins" in url.namespaces and request.path.startswith("/orga")
        ):
            response = self._handle_orga_url(request, url)
            if response:
                return response
        elif (
            event
            and request.event.custom_domain
            and not request.uses_custom_domain
            and not is_exempt
        ):
            response = redirect(
                urljoin(request.event.custom_domain, request.get_full_path())
            )
            response["Access-Control-Allow-Origin"] = "*"
            return response
        if event:
            with scope(event=event):
                response = self.get_response(request)
        else:
            response = self.get_response(request)

        if is_exempt and "Access-Control-Allow-Origin" not in response:
            response["Access-Control-Allow-Origin"] = "*"
        return response

    def _select_locale(self, request):
        supported = (
            request.event.locales
            if (hasattr(request, "event") and request.event)
            else list(settings.LANGUAGES_INFORMATION)
        )
        language = (
            self._language_from_request(request, supported)
            or self._language_from_cookie(request, supported)
            or self._language_from_user(request, supported)
            or self._language_from_browser(request, supported)
            or self._language_from_event(request, supported)
            or settings.LANGUAGE_CODE
        )
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

        with suppress(zoneinfo.ZoneInfoNotFoundError):
            if hasattr(request, "event") and request.event:
                tzname = request.event.timezone
            elif request.user.is_authenticated:
                tzname = request.user.timezone
            else:
                tzname = settings.TIME_ZONE
            timezone.activate(zoneinfo.ZoneInfo(tzname))
            request.timezone = tzname

    def _language_from_browser(self, request, supported):
        accept_value = request.headers.get("Accept-Language", "")
        for accept_lang, _ in parse_accept_lang_header(accept_value):
            if accept_lang == "*":
                break

            if not language_code_re.search(accept_lang):
                continue

            accept_lang = self._validate_language(accept_lang, supported)
            if accept_lang:
                return accept_lang

    def _language_from_cookie(self, request, supported):
        cookie_value = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        return self._validate_language(cookie_value, supported)

    def _language_from_user(self, request, supported):
        if request.user.is_authenticated:
            return self._validate_language(request.user.locale, supported)

    def _language_from_request(self, request, supported):
        lang = request.GET.get("lang")
        if lang:
            lang = self._validate_language(lang, supported)
            if lang:
                request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = lang
                return lang

    def _language_from_event(self, request, supported):
        if hasattr(request, "event") and request.event:
            return self._validate_language(request.event.locale, supported)

    @staticmethod
    def _validate_language(value, supported):
        with suppress(LookupError):
            value = get_supported_language_variant(value)
            if value in supported:
                return value
