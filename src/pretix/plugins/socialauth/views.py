import logging
from urllib.parse import urlencode, urlparse, urlunparse

from allauth.socialaccount.adapter import get_adapter
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

from pretix.base.models import User
from pretix.control.views.auth import process_login_and_set_cookie
from pretix.helpers.urls import build_absolute_uri

logger = logging.getLogger(__name__)
adapter = get_adapter()


def oauth_login(request, provider):
    base_url = adapter.get_provider(request, provider).get_login_url(request)
    query_params = {
        "next": build_absolute_uri("plugins:socialauth:social.oauth.return")
    }
    parsed_url = urlparse(base_url)
    updated_url = parsed_url._replace(query=urlencode(query_params))
    return redirect(urlunparse(updated_url))


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
