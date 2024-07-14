import jwt
import requests

from allauth.socialaccount.providers.oauth2.views import OAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2LoginView, OAuth2CallbackView)
from allauth.socialaccount.internal import jwtkit
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.db import IntegrityError


class EventyayTicketOAuth2Adapter(OAuth2Adapter):
    provider_id = 'eventyay'

    @property
    def access_token_url(self):
        config = self.get_provider().get_openid_config()
        return config['token_endpoint']

    @property
    def authorize_url(self):
        config = self.get_provider().get_openid_config()
        return config['authorization_endpoint']

    @property
    def profile_url(self):
        config = self.get_provider().get_openid_config()
        return config['userinfo_endpoint']

    def complete_login(self, request, app, token, **kwargs):
        headers = {'Authorization': f'Bearer {token.token}'}
        response = requests.get(self.profile_url, headers=headers)
        response.raise_for_status()
        extra_data = response.json()
        return self.get_provider().sociallogin_from_response(request, extra_data)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        try:
            user = super().save_user(request, sociallogin, form)
        except IntegrityError as e:
            # bypass the error if the user with this email created in eventyay-talk before
            pass


oauth2_login = OAuth2LoginView.adapter_view(EventyayTicketOAuth2Adapter)
oauth2_callback = OAuth2CallbackView.adapter_view(EventyayTicketOAuth2Adapter)
