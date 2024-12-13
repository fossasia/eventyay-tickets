import logging

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

from pretix.base.models import User
from pretix.control.views.auth import process_login_and_set_cookie

logger = logging.getLogger(__name__)


def oauth_return(request):
    try:
        user, _ = User.objects.get_or_create(
            email=request.user.email,
            defaults={
                'locale': getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE),
                'timezone': getattr(request, 'timezone', settings.TIME_ZONE),
                'auth_backend': 'native',
                'password': '',
            },
        )
        return process_login_and_set_cookie(request, user, False)
    except AttributeError:
        messages.error(
            request, _('Error while authorizing: no email address available.')
        )
        logger.error('Error while authorizing: user has no email address.')
        return redirect('control:auth.login')
