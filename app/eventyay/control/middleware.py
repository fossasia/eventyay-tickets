import logging
from urllib.parse import quote, urljoin

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME, logout
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, redirect, resolve_url
from django.template.response import TemplateResponse
from django.urls import get_script_prefix, resolve, reverse
from django.utils.encoding import force_str
from django.utils.translation import gettext as _
from django_scopes import scope

from eventyay.base.models import Event, Organizer
from eventyay.base.models.auth import SuperuserPermissionSet, User
from eventyay.helpers.security import (
    SessionInvalid,
    SessionReauthRequired,
    assert_session_valid,
)

logger = logging.getLogger(__name__)


class PermissionMiddleware:
    """
    This middleware enforces all requests to the control app to require login.
    Additionally, it enforces all requests to "control:event." URLs
    to be for an event the user has basic access to.
    """

    EXCEPTIONS = (
        'auth.login',
        'auth.login.2fa',
        'auth.register',
        'auth.forgot',
        'auth.forgot.recover',
        'auth.invite',
        'user.settings.notifications.off',
        'oauth2_provider',
    )

    EXCEPTIONS_2FA = (
        'eventyay_common:account.2fa',
        'eventyay_common:account.2fa.add',
        'eventyay_common:account.2fa.enable',
        'eventyay_common:account.2fa.disable',
        'eventyay_common:account.2fa.regenemergency',
        'eventyay_common:account.2fa.confirm.totp',
        'eventyay_common:account.2fa.confirm.webauthn',
        'eventyay_common:account.2fa.delete',
        'auth.logout',
        'user.reauth',
    )

    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__()

    def _login_redirect(self, request: HttpRequest) -> HttpResponseRedirect:
        """Build a response to redirect the user to the login page.

        After logging-in, user should be redirected to original attempted URL with this exception:
        - If the original attempted URL is "tickets/control", redirect to "/tickets/common" instead.
        """
        # urlparse chokes on lazy objects in Python 3, force to str
        resolved_login_url = force_str(resolve_url(settings.LOGIN_URL_CONTROL))
        unwanted_path = reverse('control:index')
        if request.path.startswith(unwanted_path):
            next_url = reverse('eventyay_common:dashboard')
        else:
            next_url = request.path
        logger.info('URL to redirect to, after logging-in: %s', next_url)
        from django.contrib.auth.views import redirect_to_login

        logger.info('Redirect to login page: %s', resolved_login_url)
        return redirect_to_login(next_url, resolved_login_url, REDIRECT_FIELD_NAME)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        url = resolve(request.path_info)
        url_name = url.url_name

        if not request.path.startswith(get_script_prefix() + 'control') and not request.path.startswith(
            get_script_prefix() + 'common'
        ):
            # This middleware should only touch the /control subpath
            return self.get_response(request)

        if hasattr(request, 'organizer'):
            if not settings.DEBUG:
                new_url = urljoin(settings.SITE_URL, request.get_full_path())
                bau = request.build_absolute_uri()
                if new_url != bau:
                    logger.info('Organizer info is seen, redirecting to: %s', new_url)
                    logger.info('build_absolute_uri was: %s', bau)
                    return redirect(new_url)
            else:
                logger.debug(
                    "Organizer info detected, but skipping redirect in DEBUG for host=%s",
                    request.get_host(),
                )

        # Add this condition to bypass middleware for 'oauth/' and its sub-URLs
        # TODO: Instead of hardcoding URL, we should check the `request.resolver_match`.
        if request.path.startswith(get_script_prefix() + 'common/oauth2/'):
            return self.get_response(request)

        if url_name in self.EXCEPTIONS:
            return self.get_response(request)
        if not request.user.is_authenticated:
            return self._login_redirect(request)

        try:
            # If this logic is updated, make sure to also update the logic in eventyay/api/auth/permission.py
            assert_session_valid(request)
        except SessionInvalid:
            logout(request)
            return self._login_redirect(request)
        except SessionReauthRequired:
            if url_name not in ('user.reauth', 'auth.logout'):
                return redirect(reverse('control:user.reauth') + '?next=' + quote(request.get_full_path()))

        if not request.user.require_2fa and settings.EVENTYAY_OBLIGATORY_2FA and url_name not in self.EXCEPTIONS_2FA:
            page_2fa_setting_url = reverse('eventyay_common:account.2fa')
            logger.info(
                'This site requires 2FA but user doesnot have one. Redirect to 2FA setting page: %s',
                page_2fa_setting_url,
            )
            return redirect(page_2fa_setting_url)

        if 'event' in url.kwargs and 'organizer' in url.kwargs:
            with scope(organizer=None):
                event = (
                    Event.objects.filter(
                        slug=url.kwargs['event'],
                        organizer__slug=url.kwargs['organizer'],
                    )
                    .select_related('organizer')
                    .first()
                )
            request.event = event
            if not event or not request.user.has_event_permission(event.organizer, event, request=request):
                raise Http404(_('The selected event was not found or you have no permission to administrate it.'))
            logger.info(
                'Found organizer %s from event %s. Attaching to request.',
                event.organizer.slug,
                event.slug,
            )
            request.organizer = event.organizer
            if request.user.has_active_staff_session(request.session.session_key):
                request.eventpermset = SuperuserPermissionSet()
            else:
                request.eventpermset = request.user.get_event_permission_set(event.organizer, event)
        elif 'organizer' in url.kwargs:
            organizer = Organizer.objects.filter(
                slug=url.kwargs['organizer'],
            ).first()
            if organizer:
                logger.info(
                    'Found organizer from kwargs %s. Attaching to request.',
                    organizer.slug,
                )
            request.organizer = organizer
            if not organizer or not request.user.has_organizer_permission(organizer, request=request):
                raise Http404(_('The selected organizer was not found or you have no permission to administrate it.'))
            if request.user.has_active_staff_session(request.session.session_key):
                request.orgapermset = SuperuserPermissionSet()
            else:
                request.orgapermset = request.user.get_organizer_permission_set(organizer)

        with scope(organizer=getattr(request, 'organizer', None)):
            r = self.get_response(request)
            if isinstance(r, TemplateResponse):
                r = r.render()
            return r


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(get_script_prefix() + 'control') and request.user.is_authenticated:
            if getattr(request.user, 'is_hijacked', False):
                hijack_history = request.session.get('hijack_history', False)
                hijacker = get_object_or_404(User, pk=hijack_history[0])
                ss = hijacker.get_active_staff_session(request.session.get('hijacker_session'))
                if ss:
                    ss.logs.create(
                        url=request.path,
                        method=request.method,
                        impersonating=request.user,
                    )
            else:
                ss = request.user.get_active_staff_session(request.session.session_key)
                if ss:
                    ss.logs.create(url=request.path, method=request.method)

        response = self.get_response(request)
        return response
