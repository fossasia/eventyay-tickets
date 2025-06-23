import time
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.middleware import (
    SessionMiddleware as BaseSessionMiddleware,
)
from django.core.exceptions import DisallowedHost
from django.db.models import Q
from django.http import Http404
from django.http.request import split_domain_port
from django.middleware.csrf import CSRF_SESSION_KEY
from django.middleware.csrf import CsrfViewMiddleware as BaseCsrfMiddleware
from django.shortcuts import redirect
from django.urls import resolve
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date

from pretalx.event.models.event import Event

LOCAL_HOST_NAMES = ("testserver", "localhost", "127.0.0.1")
ANY_DOMAIN_ALLOWED = ("robots.txt", "redirect")


class MultiDomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def get_host(request):
        # We try three options, in order of decreasing preference.
        if settings.USE_X_FORWARDED_HOST and ("X-Forwarded-Host" in request.headers):
            host = request.headers["X-Forwarded-Host"]
        elif "Host" in request.headers:
            host = request.headers["Host"]
        else:
            # Reconstruct the host using the algorithm from PEP 333.
            host = request.META["SERVER_NAME"]
            server_port = str(request.META["SERVER_PORT"])
            if server_port != ("443" if request.is_secure() else "80"):
                host = f"{host}:{server_port}"
        return host

    def process_request(self, request):
        host = self.get_host(request)
        domain, port = split_domain_port(host)
        default_domain, _ = split_domain_port(settings.SITE_NETLOC)

        request.host = domain
        request.port = int(port) if port else None
        request.uses_custom_domain = False

        resolved = resolve(request.path_info)
        if resolved.url_name in ANY_DOMAIN_ALLOWED or request.path_info.startswith(
            "/api/"
        ):
            return None
        event_slug = resolved.kwargs.get("event")
        if event_slug:
            try:
                event = Event.objects.get(slug__iexact=event_slug)
            except (Event.DoesNotExist, ValueError):
                # A ValueError can happen if the event slug contains malicious input
                # like NUL bytes. We return a 404 here to avoid leaking information.
                raise Http404()
            request.event = event
            if event.custom_domain:
                custom_domain = urlparse(event.custom_domain)
                event_domain, event_port = split_domain_port(custom_domain.netloc)
                if event_domain == domain and event_port == port:
                    request.uses_custom_domain = True
                    return None
                elif domain == default_domain and not request.path.startswith("/orga"):
                    return redirect(
                        urljoin(event.urls.base.full(), request.get_full_path())
                    )
            elif domain == default_domain:
                return None
            # We are on an event page, but under the incorrect domain. Redirecting
            # to the proper domain would leak information, so we will show a 404
            # instead.
            if not request.path.startswith("/orga"):
                raise Http404()

        if domain == default_domain:
            return None

        if settings.DEBUG or domain in LOCAL_HOST_NAMES:
            return None

        if request.path_info.startswith("/orga"):  # pragma: no cover
            return redirect(urljoin(settings.SITE_URL, request.get_full_path()))

        # If this domain is used as custom domain, but we are trying to view a
        # non-event page, try to redirect to the most recent event instead.
        events = Event.objects.filter(
            Q(custom_domain=f"{request.scheme}://{domain}")
            | Q(custom_domain=f"{request.scheme}://{host}"),
        ).order_by("-date_from")
        if events:
            request.uses_custom_domain = True
            public_event = events.filter(is_public=True).first()
            if public_event:
                return redirect(public_event.urls.base.full())
            # This domain is configured for an event, but does not have a public event
            # yet. We will show the start page instead of a confusing (to organisers)
            # 404.
            return
        # This domain is not configured for any event, so we will show a 404.
        # Note that this should not occur on a well-configured host, as the web server
        # should make sure that a domain is configured before serving it (as it needs to
        # provide an SSL certificate for it, etc.), but of course this can still happen
        # when caches (DNS or otherwise) are involved.
        raise DisallowedHost(f"Unknown host: {host}")

    def process_response(self, request, response):
        if request.path.startswith("/orga"):
            if (event := getattr(request, "event", None)) and event.custom_domain:
                # We need to update the CSP in order to make our fancy login form work
                response._csp_update = getattr(response, "_csp_update", None) or {}
                response._csp_update["form-action"] = [event.urls.base.full()]
        return response

    def __call__(self, request):
        response = self.process_request(request)
        if response:
            # This is used to return redirects directly
            return response
        return self.process_response(request, self.get_response(request))


class SessionMiddleware(BaseSessionMiddleware):
    """We override the default implementation from Django.

    We do this because we need to handle cookie domains differently
    depending on whether we are on the main domain or a custom domain.
    """

    def __init__(self, get_response, *args, **kwargs):
        super().__init__(*args, get_response=get_response, **kwargs)
        self.get_response = get_response

    def process_response(self, request, response):
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:  # pragma: no cover
            pass
        else:
            # First check if we need to delete this cookie.
            # The session should be deleted only if the session is entirely empty
            if settings.SESSION_COOKIE_NAME in request.COOKIES and empty:
                response.delete_cookie(settings.SESSION_COOKIE_NAME)
                return response
            if accessed:
                patch_vary_headers(response, ("Cookie",))
            if modified or settings.SESSION_SAVE_EVERY_REQUEST:
                max_age = None
                expires = None
                if not request.session.get_expire_at_browser_close():
                    max_age = request.session.get_expiry_age()
                    expires_time = time.time() + max_age
                    expires = http_date(expires_time)
                # Save the session data and refresh the client cookie.
                # Skip session save for 500 responses, refs #3881.
                if response.status_code != 500:
                    try:
                        request.session.save()
                    except UpdateError:  # pragma: no cover
                        request.session.create()
                    response.set_cookie(
                        settings.SESSION_COOKIE_NAME,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=get_cookie_domain(request),
                        path=settings.SESSION_COOKIE_PATH,
                        secure=request.scheme == "https",
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                    )
        return response

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        return self.process_response(request, response)


class CsrfViewMiddleware(BaseCsrfMiddleware):
    """We override the default implementation from Django.

    We do this because we need to handle cookie domains differently
    depending on whether we are on the main domain or a custom domain.
    """

    def _set_cookie_csrf(self, request, response):
        # If CSRF_COOKIE is unset, then CsrfViewMiddleware.process_view was
        # never called, probably because a request middleware returned a response
        # (for example, contrib.auth redirecting to a login page).
        if settings.CSRF_USE_SESSIONS:
            if request.session.get(CSRF_SESSION_KEY) != request.META["CSRF_COOKIE"]:
                request.session[CSRF_SESSION_KEY] = request.META["CSRF_COOKIE"]
        else:
            # Set the CSRF cookie even if it's already set, so we renew
            # the expiry timer.
            response.set_cookie(
                settings.CSRF_COOKIE_NAME,
                request.META["CSRF_COOKIE"],
                max_age=settings.CSRF_COOKIE_AGE,
                domain=get_cookie_domain(request),
                path=settings.CSRF_COOKIE_PATH,
                secure=request.scheme == "https",
                httponly=settings.CSRF_COOKIE_HTTPONLY,
            )
            # Content varies with the CSRF cookie, so set the Vary header.
            patch_vary_headers(response, ("Cookie",))


def get_cookie_domain(request):
    if "." not in request.host:
        # As per spec, browsers do not accept cookie domains without dots in it,
        # e.g. "localhost", see http://curl.haxx.se/rfc/cookie_spec.html
        return None

    default_domain, _ = split_domain_port(settings.SITE_NETLOC)
    # If we are on our main domain, set the cookie domain the user has chosen. Else
    # we are on an organiser's custom domain, set no cookie domain, as we do not want
    # the cookies to be present on any other domain. Setting an explicit value can be
    # dangerous, see http://erik.io/blog/2014/03/04/definitive-guide-to-cookie-domains/
    return settings.SESSION_COOKIE_DOMAIN if request.host == default_domain else None
