import functools
import logging
from typing import cast

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount import app_settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

logger = logging.getLogger(__name__)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    # Override to setup User-Agent to follow Wikimedia policy
    # https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
    def get_requests_session(self):
        # The self.request was populated by BaseAdapter.
        dj_request = cast(HttpRequest, self.request)
        site_url = dj_request.build_absolute_uri('/')
        try:
            contact = settings.ADMINS[0][1]
        except (AttributeError, IndexError):
            contact = 'webmaster@eventyay.com'
        user_agent = f'eventyay/1.0 ({site_url}; {contact})'

        import requests

        session = requests.Session()
        session.headers.update({'User-Agent': user_agent})
        session.request = functools.partial(session.request, timeout=app_settings.REQUESTS_TIMEOUT)
        return session

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        logger.error('Error while authorizing with %s: %s - %s', provider, error, exception)
        raise ImmediateHttpResponse(HttpResponseRedirect(reverse('control:index')))
