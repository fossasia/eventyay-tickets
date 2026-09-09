import hashlib
import logging
import smtplib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import BadHeaderError, EmailMessage
from django.core.validators import validate_email
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views import View

from eventyay.base.services.turnstile import (
    TURNSTILE_ERROR_MESSAGE,
    TURNSTILE_FAILED_MESSAGE,
    TURNSTILE_MISCONFIGURED_MESSAGE,
    get_turnstile_settings,
    is_turnstile_enabled_for_action,
    verify_turnstile_token,
)
from eventyay.helpers.http import get_client_ip

from . import EventViewMixin


logger = logging.getLogger(__name__)

_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 600  # 10 minutes


class ContactOrganizerView(EventViewMixin, View):
    """Accept a contact-organizer message and forward it via email."""

    def _is_rate_limited(self, request):
        if not settings.HAS_REDIS:
            return False
        client_ip = get_client_ip(request)
        if not client_ip:
            return False
        from django_redis import get_redis_connection
        from redis.exceptions import RedisError
        key = f'contact_ratelimit_{hashlib.sha1(client_ip.encode()).hexdigest()}'
        try:
            rc = get_redis_connection('redis')
            count = rc.get(key)
            if count and int(count) >= _RATE_LIMIT_MAX:
                return True
            if rc.incr(key) == 1:
                rc.expire(key, _RATE_LIMIT_WINDOW)
        except RedisError:
            logger.exception('Contact form rate-limit check failed; allowing request')
        return False

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'success': False, 'error': _('You must be logged in to send a message.')},
                status=401,
            )

        message = request.POST.get('message', '').strip()
        send_copy = request.POST.get('send_copy') == 'on'

        sender_email = request.user.email
        if not sender_email:
            return JsonResponse(
                {'success': False, 'error': _('Your account must have an email address to send messages.')},
                status=400,
            )

        if not message:
            return JsonResponse(
                {'success': False, 'error': _('Please enter a message.')},
                status=400,
            )

        if len(message) < 10:
            return JsonResponse(
                {'success': False, 'error': _('Your message is too short (minimum 10 characters).')},
                status=400,
            )

        if len(message) > 5000:
            return JsonResponse(
                {'success': False, 'error': _('Your message is too long (maximum 5000 characters).')},
                status=400,
            )

        try:
            validate_email(sender_email)
        except ValidationError:
            return JsonResponse(
                {'success': False, 'error': _('Your account email address is invalid.')},
                status=400,
            )

        if self._is_rate_limited(request):
            return JsonResponse(
                {
                    'success': False,
                    'error': _('Too many messages sent. Please wait a few minutes before trying again.'),
                },
                status=429,
            )

        contact_email = request.event.contact_form_recipient_email()

        if not request.event.show_contact_form():
            return JsonResponse(
                {'success': False, 'error': _('No contact email configured for this event.')},
                status=400,
            )

        if not contact_email:
            return JsonResponse(
                {'success': False, 'error': _('No contact email configured for this event.')},
                status=400,
            )

        if is_turnstile_enabled_for_action('contact', request):
            cfg = get_turnstile_settings()
            if not cfg['site_key'] or not cfg['secret_key']:
                return JsonResponse(
                    {'success': False, 'error': str(TURNSTILE_MISCONFIGURED_MESSAGE)},
                    status=400,
                )

            token = request.POST.get('cf-turnstile-response')
            if not token:
                return JsonResponse(
                    {'success': False, 'error': str(TURNSTILE_ERROR_MESSAGE)},
                    status=400,
                )
            client_ip = get_client_ip(request)
            valid, error_code = verify_turnstile_token(
                token,
                remote_ip=client_ip,
                expected_action='contact',
            )
            if not valid:
                if error_code == 'missing-secret':
                    return JsonResponse(
                        {'success': False, 'error': str(TURNSTILE_MISCONFIGURED_MESSAGE)},
                        status=400,
                    )
                return JsonResponse(
                    {'success': False, 'error': str(TURNSTILE_FAILED_MESSAGE)},
                    status=400,
                )

        subject = _('Message from attendee – {event}').format(
            event=str(request.event.name),
        )

        try:
            backend = request.event.get_mail_backend()
            from_addr = (
                request.event.settings.get('mail_from')
                or settings.DEFAULT_FROM_EMAIL
            )
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_addr,
                to=[contact_email],
                reply_to=[sender_email],
            )
            if send_copy:
                email.bcc = [sender_email]
            backend.send_messages([email])
        except (smtplib.SMTPException, BadHeaderError, ConnectionError, OSError) as e:
            logger.exception('Failed to send contact organizer email')
            error_msg = _('Failed to send message. Please try again later.')
            if isinstance(e, BadHeaderError):
                error_msg = _('Failed to send message: Invalid email header.')
            elif isinstance(e, (ConnectionError, OSError)):
                error_msg = _('Failed to send message: Network error communicating with mail server.')
            elif isinstance(e, smtplib.SMTPException):
                error_msg = _('Failed to send message: Mail server rejected the message.')
            return JsonResponse(
                {'success': False, 'error': error_msg},
                status=500,
            )

        return JsonResponse({'success': True})
