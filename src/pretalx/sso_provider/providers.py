import requests

from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider
from allauth.socialaccount.providers.base import AuthAction, ProviderAccount
from allauth.socialaccount.app_settings import QUERY_EMAIL
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.helpers import render_authentication_error
from django.conf import settings
from django.urls import reverse

from .views import EventyayTicketOAuth2Adapter


class Scope(object):
    OPEN_ID = "openid"
    EMAIL = "email"
    PROFILE = "profile"


class EventYayTicketAccount(ProviderAccount):

    def get_profile_url(self):
        return self.account.extra_data.get("link")

    def get_avatar_url(self):
        return self.account.extra_data.get("picture")

    def to_str(self):
        dflt = super(GoogleAccount, self).to_str()
        return self.account.extra_data.get("name", dflt)


class EventyayProvider(OAuth2Provider):
    id = 'eventyay'
    name = 'Eventyay'
    account_class = EventYayTicketAccount
    oauth2_adapter_class = EventyayTicketOAuth2Adapter

    def get_openid_config(self):
        try:
            response = requests.get(settings.EVENTYAY_TICKET_SSO_WELL_KNOW_URL
                                    .format(org=self.request.session.get('org')))
            response.raise_for_status()
        except:
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
        url = reverse(self.id + "_login")
        if kwargs:
            url = url + "?" + urlencode(kwargs)
        return url


provider_classes = [EventyayProvider]
