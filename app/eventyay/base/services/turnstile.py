import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django import forms
from django.core.cache import cache
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from eventyay.base.settings import GlobalSettingsObject
from eventyay.helpers.http import get_client_ip


logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
TURNSTILE_ERROR_MESSAGE = _('Please complete the security verification before continuing.')
TURNSTILE_FAILED_MESSAGE = _('Security verification failed. Please try again.')
TURNSTILE_MISCONFIGURED_MESSAGE = _(
    'Security verification is currently unavailable. Please contact the site administrator.'
)

FAILED_LOGIN_CACHE_PREFIX = 'turnstile_failed_login:'
FAILED_LOGIN_CACHE_TIMEOUT = 1800  # 30 minutes


def get_turnstile_settings():
    """Retrieve global Turnstile settings."""
    gs = GlobalSettingsObject().settings
    provider = gs.get('anti_abuse_provider', as_type=str, default='disabled') or 'disabled'
    site_key = gs.get('turnstile_site_key', as_type=str, default='') or ''
    secret_key = gs.get('turnstile_secret_key', as_type=str, default='') or ''
    return {
        'provider': provider,
        'enabled': provider == 'turnstile',
        'site_key': site_key,
        'secret_key': secret_key,
        'on_registration': bool(gs.get('turnstile_on_registration', as_type=bool, default=False)),
        'login_mode': gs.get('turnstile_login_mode', as_type=str, default='disabled') or 'disabled',
        'failed_login_threshold': int(gs.get('turnstile_failed_login_threshold', as_type=int, default=3) or 3),
        'on_password_reset': bool(gs.get('turnstile_on_password_reset', as_type=bool, default=False)),
        'on_organizer_create': bool(gs.get('turnstile_on_organizer_create', as_type=bool, default=False)),
        'on_contact': bool(gs.get('turnstile_on_contact', as_type=bool, default=False)),
    }


def _get_failed_login_cache_key(request: HttpRequest | None) -> str | None:
    if not request:
        return None
    ip = get_client_ip(request)
    if not ip:
        return None
    hashed_ip = hashlib.sha256(ip.encode('utf-8')).hexdigest()
    return f'{FAILED_LOGIN_CACHE_PREFIX}{hashed_ip}'


def get_failed_login_count(request: HttpRequest | None) -> int:
    """Get the number of recent failed login attempts for this client IP."""
    key = _get_failed_login_cache_key(request)
    if not key:
        return 0
    try:
        val = cache.get(key, 0)
        return int(val or 0)
    except (ValueError, TypeError):
        return 0
    except (OSError, ConnectionError, TimeoutError) as exc:
        logger.warning('Failed to retrieve failed login counter from cache: %s', exc)
        return 0


def record_failed_login_attempt(request: HttpRequest | None) -> int:
    """Increment the failed login attempts for this client IP atomically."""
    key = _get_failed_login_cache_key(request)
    if not key:
        return 0
    try:
        if not cache.add(key, 1, timeout=FAILED_LOGIN_CACHE_TIMEOUT):
            try:
                return cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=FAILED_LOGIN_CACHE_TIMEOUT)
                return 1
        return 1
    except (OSError, ConnectionError, TimeoutError, ValueError, TypeError) as exc:
        logger.warning('Failed to record failed login attempt in cache: %s', exc)
        return 0


def reset_failed_login_attempts(request: HttpRequest | None) -> None:
    """Reset the failed login counter upon successful login."""
    key = _get_failed_login_cache_key(request)
    if not key:
        return
    try:
        cache.delete(key)
    except (OSError, ConnectionError, TimeoutError) as exc:
        logger.warning('Failed to delete failed login counter from cache: %s', exc)


def is_turnstile_enabled_for_action(action: str, request: HttpRequest | None = None) -> bool:
    """
    Check whether Cloudflare Turnstile protection should be active for a given action.
    Actions supported: 'registration', 'login', 'password_reset', 'organizer_create', 'contact'.
    """
    cfg = get_turnstile_settings()
    if not cfg['enabled']:
        return False

    if action == 'registration':
        return cfg['on_registration']
    elif action == 'password_reset':
        return cfg['on_password_reset']
    elif action == 'organizer_create':
        return cfg['on_organizer_create']
    elif action == 'contact':
        return cfg['on_contact']
    elif action == 'login':
        mode = cfg['login_mode']
        if mode == 'always':
            return True
        elif mode == 'failed_attempts_only':
            failed_count = get_failed_login_count(request)
            return failed_count >= cfg['failed_login_threshold']
        return False

    return False


def verify_turnstile_token(
    token: str | None,
    remote_ip: str | None = None,
    expected_action: str | None = None,
    expected_hostname: str | None = None,
) -> tuple[bool, str | None]:
    """
    Verify a Cloudflare Turnstile response token with Cloudflare API.
    Optionally validates expected action and hostname returned in the verification payload.
    Returns (is_valid, error_code).
    """
    cfg = get_turnstile_settings()
    secret_key = cfg['secret_key']
    if not secret_key:
        logger.error('Turnstile verification failed: Turnstile secret key is not configured.')
        return False, 'missing-secret'

    if not token or not token.strip():
        return False, 'missing-input-response'

    payload = {
        'secret': secret_key,
        'response': token.strip(),
    }
    if remote_ip:
        payload['remoteip'] = remote_ip

    try:
        data = urllib.parse.urlencode(payload).encode('utf-8')
        req = urllib.request.Request(
            TURNSTILE_VERIFY_URL,
            data=data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Eventyay-Turnstile/1.0',
            },
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_body = response.read().decode('utf-8')
            res_data = json.loads(res_body)

        if not isinstance(res_data, dict):
            logger.warning('Cloudflare Turnstile returned non-dictionary response: %r', res_data)
            return False, 'invalid-response'

        success = bool(res_data.get('success'))
        if not success:
            error_codes = res_data.get('error-codes', [])
            if not isinstance(error_codes, list):
                error_codes = []
            logger.warning(
                'Cloudflare Turnstile token validation failed: error_codes=%s',
                error_codes,
            )
            return False, error_codes[0] if error_codes else 'invalid-input-response'

        token_action = res_data.get('action')
        if expected_action and token_action != expected_action:
            logger.warning(
                'Cloudflare Turnstile action mismatch: expected=%s, got=%s',
                expected_action,
                token_action,
            )
            return False, 'action-mismatch'

        token_hostname = res_data.get('hostname')
        if expected_hostname and token_hostname and token_hostname != expected_hostname:
            logger.warning(
                'Cloudflare Turnstile hostname mismatch: expected=%s, got=%s',
                expected_hostname,
                token_hostname,
            )
            return False, 'hostname-mismatch'

        return True, None
    except (urllib.request.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError, AttributeError):
        logger.exception('Error during Cloudflare Turnstile token verification.')
        return False, 'network-error'


class TurnstileValidationMixin:
    """Mixin for forms that require Turnstile anti-abuse verification."""

    turnstile_action = 'login'

    def clean_turnstile(self, request: HttpRequest | None = None):
        req = getattr(self, 'request', request)
        if not is_turnstile_enabled_for_action(self.turnstile_action, req):
            return

        cfg = get_turnstile_settings()
        if not cfg['site_key'] or not cfg['secret_key']:
            raise forms.ValidationError(TURNSTILE_MISCONFIGURED_MESSAGE, code='turnstile_misconfigured')

        token = None
        if req and hasattr(req, 'POST'):
            token = req.POST.get('cf-turnstile-response')
        elif hasattr(self, 'data') and self.data:
            token = self.data.get('cf-turnstile-response')

        if not token:
            raise forms.ValidationError(TURNSTILE_ERROR_MESSAGE, code='turnstile_missing')

        client_ip = get_client_ip(req) if req else None
        valid, error_code = verify_turnstile_token(
            token,
            remote_ip=client_ip,
            expected_action=self.turnstile_action,
        )
        if not valid:
            if error_code == 'missing-secret':
                raise forms.ValidationError(TURNSTILE_MISCONFIGURED_MESSAGE, code='turnstile_misconfigured')
            raise forms.ValidationError(TURNSTILE_FAILED_MESSAGE, code='turnstile_invalid')


def test_turnstile_connection(secret_key: str | None = None) -> tuple[bool, str]:
    """
    Tests connectivity to Cloudflare Turnstile API and validates the secret key.
    Returns (success: bool, message: str).
    """
    if not secret_key:
        cfg = get_turnstile_settings()
        secret_key = cfg['secret_key']

    if not secret_key:
        return False, str(_('Turnstile secret key is not configured. Please enter and save the secret key first.'))

    payload = {
        'secret': secret_key,
        'response': 'eventyay-test-connection-probe',
    }
    try:
        data = urllib.parse.urlencode(payload).encode('utf-8')
        req = urllib.request.Request(
            TURNSTILE_VERIFY_URL,
            data=data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Eventyay-Turnstile/1.0',
            },
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_body = response.read().decode('utf-8')
            res_data = json.loads(res_body)

        if not isinstance(res_data, dict):
            return False, str(_('Cloudflare Turnstile returned an invalid response.'))

        if res_data.get('success'):
            return True, str(_('Cloudflare Turnstile connection test successful!'))

        error_codes = res_data.get('error-codes', [])
        if not isinstance(error_codes, list):
            error_codes = []

        if 'invalid-input-secret' in error_codes or 'missing-input-secret' in error_codes:
            return False, str(_('Connection failed: Invalid Turnstile secret key.'))

        if 'invalid-input-response' in error_codes or 'timeout-or-duplicate' in error_codes:
            return True, str(
                _('Cloudflare Turnstile connection successful! The secret key is valid and Cloudflare API is reachable.')
            )

        err_str = ', '.join(error_codes) if error_codes else 'unknown error'
        return False, str(_('Cloudflare Turnstile returned an error: %(error)s') % {'error': err_str})

    except urllib.error.HTTPError as exc:
        return False, str(_('Cloudflare Turnstile server returned HTTP error: %(status)s') % {'status': exc.code})
    except urllib.error.URLError as exc:
        return False, str(_('Could not connect to Cloudflare Turnstile servers: %(error)s') % {'error': exc.reason})
    except (TimeoutError, OSError) as exc:
        return False, str(_('Connection to Cloudflare Turnstile servers timed out: %(error)s') % {'error': exc})
    except (json.JSONDecodeError, ValueError) as exc:
        return False, str(_('Failed to parse response from Cloudflare Turnstile: %(error)s') % {'error': exc})

