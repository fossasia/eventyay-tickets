import logging
import traceback
import zoneinfo
from contextlib import suppress
from urllib.parse import quote, urljoin

import jwt
from django.conf import settings
from django.contrib.auth import login
from django.db.models import OuterRef, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, reverse
from django.urls import resolve
from django.utils import timezone, translation
from django.utils.translation.trans_real import (
    get_supported_language_variant,
    language_code_re,
    parse_accept_lang_header,
)
from django_scopes import scope, scopes_disabled

from pretalx.event.models import Event, Organiser
from pretalx.person.models import User
from pretalx.schedule.models import Schedule


logger = logging.getLogger(__name__)


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
    def _handle_login(request):
        # If the user is already authenticated, no need to auto-login

        if request.user.is_authenticated or any(
            path in request.path for path in ["/callback", "/signup"]
        ):
            return

        # Check for the presence of the SSO token
        sso_token = request.COOKIES.get("sso_token") or request.COOKIES.get(
            "customer_sso_token"
        )
        if sso_token:
            try:
                # Decode and validate the JWT token
                payload = jwt.decode(
                    sso_token, settings.SECRET_KEY, algorithms=["HS256"]
                )
                user, created = User.objects.get_or_create(email=payload["email"])
                if created:
                    user.set_unusable_password()
                logger.debug("JWT payload: %s", payload)
                upstream_name = payload.get("name", "")
                # Only update user's name if it's not set.
                if not user.name and upstream_name:
                    user.name = upstream_name
                user.is_active = True
                user.is_staff = payload.get("is_staff", False)
                user.locale = payload.get("locale", user.locale)
                user.timezone = payload.get("timezone", user.timezone)
                user.code = payload.get("customer_identifier", user.code)
                user.save()
                logger.info("Saved new data for user: %s", user.email)
                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )
            except jwt.ExpiredSignatureError as e:
                # Token expired
                logger.warning(f"SSO token expired: {str(e)}\n{traceback.format_exc()}")
                pass
            except jwt.InvalidTokenError as e:
                # Invalid token
                logger.error(f"Invalid SSO token: {str(e)}\n{traceback.format_exc()}")
                pass
            except Exception as e:
                # Invalid token
                logger.error(
                    f"Unexpected error happened: {str(e)}\n{traceback.format_exc()}"
                )
                pass

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

        event_slug = url.kwargs.get("event")
        if event_slug:
            with scopes_disabled():
                try:
                    queryset = Event.objects.prefetch_related(
                        "submissions", "extra_links", "schedules"
                    ).select_related("organiser")
                    latest_schedule_subquery = (
                        Schedule.objects.filter(
                            event=OuterRef("pk"), published__isnull=False
                        )
                        .order_by("-published")
                        .values("pk")[:1]
                    )
                    queryset = queryset.annotate(
                        _current_schedule_pk=Subquery(latest_schedule_subquery)
                    )
                    request.event = get_object_or_404(queryset, slug__iexact=event_slug)
                except ValueError:
                    # Happens mostly on malformed or malicious input
                    raise Http404()
        event = getattr(request, "event", None)

        self._handle_login(request)
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
            or self._language_from_user(request, supported)
            or self._language_from_cookie(request, supported)
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
