import logging

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpResponseRedirect
from django.urls import reverse


logger = logging.getLogger(__name__)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        logger.error('Error while authorizing with %s: %s - %s', provider, error, exception)
        raise ImmediateHttpResponse(HttpResponseRedirect(reverse('control:index')))
