import time
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.contrib.sessions.middleware import (
    SessionMiddleware as BaseSessionMiddleware,
)
from django.core.exceptions import DisallowedHost
from django.http.request import split_domain_port
from django.middleware.csrf import CsrfViewMiddleware as BaseCsrfMiddleware
from django.shortcuts import get_object_or_404, redirect
from django.urls import resolve
from django.utils.cache import patch_vary_headers
from django.utils.http import cookie_date

from pretalx.event.models import Event

LOCAL_HOST_NAMES = ('testserver', 'localhost')


class MultiDomainMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def get_host(self, request):
        # We try three options, in order of decreasing preference.
        if settings.USE_X_FORWARDED_HOST and ('HTTP_X_FORWARDED_HOST' in request.META):
            host = request.META['HTTP_X_FORWARDED_HOST']
        elif 'HTTP_HOST' in request.META:
            host = request.META['HTTP_HOST']
        else:
            # Reconstruct the host using the algorithm from PEP 333.
            host = request.META['SERVER_NAME']
            server_port = str(request.META['SERVER_PORT'])
            if server_port != ('443' if request.is_secure() else '80'):
                host = f'{host}:{server_port}'
        return host

    def process_request(self, request):
        host = self.get_host(request)
        domain, port = split_domain_port(host)
        if not domain:
            raise DisallowedHost(f'Invalid HTTP_HOST header: {host}.')

        request.host = domain
        request.port = int(port) if port else None

        event_slug = resolve(request.path).kwargs.get('event')
        if event_slug:
            event = get_object_or_404(Event, slug__iexact=event_slug)
            request.event = event
            if event.settings.custom_domain:
                custom_domain = urlparse(event.settings.custom_domain)
                event_domain, event_port = split_domain_port(custom_domain.netloc)
                if event_domain == domain and event_port == port:
                    request.uses_custom_domain = True
                    return
                else:
                    request.needs_redirect = True
                    return redirect(urljoin(event.settings.custom_domain, request.path))

        default_domain, default_port = split_domain_port(settings.SITE_NETLOC)
        if domain == default_domain:
            return

        if settings.DEBUG or domain in LOCAL_HOST_NAMES:
            return

        raise DisallowedHost(f'Unknown host: {host}')

    def __call__(self, request):
        response = self.process_request(request)
        return response or self.get_response(request)


class SessionMiddleware(BaseSessionMiddleware):
    """
    We override the default implementation from django because we need to handle
    cookie domains differently depending on whether we are on the main domain or
    a custom domain.
    """

    def __init__(self, get_response, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_response = get_response

    def process_request(self, request):
        super().process_request(request)

        if not request.session.session_key:
            # We need to create session even if we do not yet store something there, because we need the session
            # key for e.g. saving the user's cart
            request.session.create()

    def process_response(self, request, response):
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            pass
        else:
            # First check if we need to delete this cookie.
            # The session should be deleted only if the session is entirely empty
            if settings.SESSION_COOKIE_NAME in request.COOKIES and empty:
                response.delete_cookie(settings.SESSION_COOKIE_NAME)
            else:
                if accessed:
                    patch_vary_headers(response, ('Cookie',))
                if modified or settings.SESSION_SAVE_EVERY_REQUEST:
                    if request.session.get_expire_at_browser_close():
                        max_age = None
                        expires = None
                    else:
                        max_age = request.session.get_expiry_age()
                        expires_time = time.time() + max_age
                        expires = cookie_date(expires_time)
                    # Save the session data and refresh the client cookie.
                    # Skip session save for 500 responses, refs #3881.
                    if response.status_code != 500:
                        request.session.save()
                        response.set_cookie(
                            settings.SESSION_COOKIE_NAME,
                            request.session.session_key, max_age=max_age,
                            expires=expires,
                            domain=get_cookie_domain(request),
                            path=settings.SESSION_COOKIE_PATH,
                            secure=request.scheme == 'https',
                            httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        )
        return response

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        return self.process_response(request, response)


class CsrfViewMiddleware(BaseCsrfMiddleware):
    """
    We override the default implementation from django because we need to handle
    cookie domains differently depending on whether we are on the main domain or
    a custom domain.
    """

    def __init__(self, get_response, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_response = get_response

    def process_response(self, request, response):
        if getattr(response, 'csrf_processing_done', False):
            return response

        # If CSRF_COOKIE is unset, then CsrfViewMiddleware.process_view was
        # never called, probably because a request middleware returned a response
        # (for example, contrib.auth redirecting to a login page).
        if request.META.get('CSRF_COOKIE') is None:
            return response

        if not request.META.get('CSRF_COOKIE_USED', False):
            return response

        # Set the CSRF cookie even if it's already set, so we renew
        # the expiry timer.
        response.set_cookie(
            settings.CSRF_COOKIE_NAME,
            request.META['CSRF_COOKIE'],
            max_age=settings.CSRF_COOKIE_AGE,
            domain=get_cookie_domain(request),
            path=settings.CSRF_COOKIE_PATH,
            secure=request.scheme == 'https',
            httponly=settings.CSRF_COOKIE_HTTPONLY
        )
        # Content varies with the CSRF cookie, so set the Vary header.
        patch_vary_headers(response, ('Cookie',))
        response.csrf_processing_done = True
        return response

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        return self.process_response(request, response)


def get_cookie_domain(request):
    if '.' not in request.host:
        # As per spec, browsers do not accept cookie domains without dots in it,
        # e.g. "localhost", see http://curl.haxx.se/rfc/cookie_spec.html
        return None

    default_domain, default_port = split_domain_port(settings.SITE_NETLOC)
    if request.host == default_domain:
        # We are on our main domain, set the cookie domain the user has chosen
        return settings.SESSION_COOKIE_DOMAIN
    else:
        # We are on an organizer's custom domain, set no cookie domain, as we do not want
        # the cookies to be present on any other domain. Setting an explicit value can be
        # dangerous, see http://erik.io/blog/2014/03/04/definitive-guide-to-cookie-domains/
        return None
