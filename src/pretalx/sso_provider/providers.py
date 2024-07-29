import logging
import requests
from urllib.parse import urlencode

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.helpers import render_authentication_error
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider
from django.conf import settings
from django.urls import reverse

from .views import EventyayTicketOAuth2Adapter

logger = logging.getLogger(__name__)

class Scope(object):
    OPEN_ID = "openid"
    EMAIL = "email"
    PROFILE = "profile"


class EventYayTicketAccount(ProviderAccount):

    def get_profile_url(self):
        return self.account.extra_data.get("link")

    def get_avatar_url(self):
        return self.account.extra_data.get("picture")


class EventyayProvider(OAuth2Provider):
    id = 'eventyay'
    name = 'Eventyay'
    account_class = EventYayTicketAccount
    oauth2_adapter_class = EventyayTicketOAuth2Adapter

    def __init__(self, request, app=None):
        if hasattr(request, 'event'):
            app = SocialApp.objects.get(provider=request.event.organiser.slug)
            self.id = request.event.organiser.slug
        elif request.session.get('org') is not None:
            app = SocialApp.objects.get(provider=request.session.get('org'))
            self.id = request.session.get('org')
        super(EventyayProvider, self).__init__(request, app=app)

    def get_openid_config(self):
        try:
            response = requests.get(settings.EVENTYAY_TICKET_SSO_WELL_KNOW_URL
                                    .format(org=self.request.session.get('org')))
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Error when getting openid config: {e}")
            raise ImmediateHttpResponse(
                render_authentication_error(self.request,
                                            'Error happened when trying get configurations from Eventyay-ticket'))
        return response.json()

    def get_default_scope(self):
        scope = [Scope.PROFILE]
        scope.append(Scope.EMAIL)
        scope.append(Scope.OPEN_ID)
        return scope

    def extract_uid(self, data):
        if "sub" in data:
            return data["sub"]
        return data["id"]

    def extract_common_fields(self, data):
        return dict(email=data.get('email'),
                    username=data.get('name'))

    def extract_email_addresses(self, data):
        ret = []
        email = data.get("email")
        if email:
            verified = bool(data.get("email_verified") or data.get("verified_email"))
            ret.append(EmailAddress(email=email, verified=verified, primary=True))
        return ret

    def get_login_url(self, request, **kwargs):
        current_event = request.event
        request.session['org'] = current_event.organiser.slug
        url = reverse("eventyay_login")  # Base login url for sso with eventyay-ticker
        if kwargs:
            url = url + "?" + urlencode(kwargs)
        return url


provider_classes = [EventyayProvider]
