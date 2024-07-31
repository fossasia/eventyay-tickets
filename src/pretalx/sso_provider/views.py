import requests

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.oauth2.views import OAuth2Adapter
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2LoginView, OAuth2CallbackView)
from allauth.utils import build_absolute_uri
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.urls import NoReverseMatch
from django.urls import reverse


class EventyayTicketOAuth2Adapter(OAuth2Adapter):

    def __init__(self, request):
        if request.session.get('org') is not None:
            self.provider_id = request.session.get('org')
        else:
            self.provider_id = 'eventyay'
        super().__init__(request)

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

    def get_callback_url(self, request, app):
        try:
            callback_url = reverse(self.provider_id + "_callback")
        except NoReverseMatch as e:
            callback_url = reverse('eventyay_callback') # Default call back url
        protocol = self.redirect_uri_protocol
        return build_absolute_uri(request, callback_url, protocol)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def get_provider(self, request, provider, client_id=None):
        """Looks up a `provider`, supporting subproviders by looking up by
        `provider_id`.
        """
        from allauth.socialaccount.providers import registry

        try:
            provider_class = registry.get_class(provider)
            if provider_class is None or provider_class.uses_apps:
                app = self.get_app(request, provider=provider, client_id=client_id)
                if not provider_class:
                    provider_class = registry.get_class(app.provider)
                if not provider_class:
                    raise ImproperlyConfigured("unknown provider: %s", app.provider)
                return provider_class(request, app=app)
            elif provider_class:
                assert not provider_class.uses_apps
                return provider_class(request, app=None)
            else:
                raise ImproperlyConfigured("unknown provider: %s", provider)
        except ImproperlyConfigured as e:
            app = self.get_app(request, provider=provider, client_id=client_id)
            if app is not None:
                provider_class = registry.get_class('eventyay')  # Get default custom provider
                return provider_class(request, app=app)
            else:
                raise ImproperlyConfigured("unknown provider: " + app.provider)

    def save_user(self, request, sociallogin, form=None):
        try:
            sociallogin.user.code = sociallogin.account.extra_data.get('sub')
            user = super().save_user(request, sociallogin, form)
        except IntegrityError as e:
            # bypass the error if the user with this email created in eventyay-talk
            # before
            pass


oauth2_login = OAuth2LoginView.adapter_view(EventyayTicketOAuth2Adapter)
oauth2_callback = OAuth2CallbackView.adapter_view(EventyayTicketOAuth2Adapter)
