import hashlib
import time

from django.conf import settings


class SessionInvalid(Exception):  # NOQA: N818
    pass


class SessionReauthRequired(Exception):  # NOQA: N818
    pass


def get_user_agent_hash(request):
    return hashlib.sha256(request.headers['User-Agent'].encode()).hexdigest()


def assert_session_valid(request):
    if not settings.EVENTYAY_LONG_SESSIONS or not request.session.get('eventyay_auth_long_session', False):
        last_used = request.session.get('eventyay_auth_last_used', time.time())
        if (
            time.time() - request.session.get('eventyay_auth_login_time', time.time())
            > settings.EVENTYAY_SESSION_TIMEOUT_ABSOLUTE
        ):
            request.session['eventyay_auth_login_time'] = 0
            raise SessionInvalid()
        if time.time() - last_used > settings.EVENTYAY_SESSION_TIMEOUT_RELATIVE:
            raise SessionReauthRequired()

    if 'User-Agent' in request.headers:
        if 'pinned_user_agent' in request.session:
            if request.session.get('pinned_user_agent') != get_user_agent_hash(request):
                raise SessionInvalid()
        else:
            request.session['pinned_user_agent'] = get_user_agent_hash(request)

    request.session['eventyay_auth_last_used'] = int(time.time())
    return True
