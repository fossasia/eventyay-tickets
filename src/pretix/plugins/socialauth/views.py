import logging
from enum import StrEnum
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View
from pydantic import ValidationError

from pretix.base.models import User
from pretix.base.settings import GlobalSettingsObject
from pretix.control.permissions import AdministratorPermissionRequiredMixin
from pretix.control.views.auth import process_login_and_set_cookie
from pretix.helpers.urls import build_absolute_uri

from .schemas.login_providers import LoginProviders

logger = logging.getLogger(__name__)
adapter = get_adapter()


class OAuthLoginView(View):
    def get(self, request: HttpRequest, provider: str) -> HttpResponse:
        self.set_oauth2_params(request)

        gs = GlobalSettingsObject()
        client_id = (
            gs.settings.get("login_providers", as_type=dict)
            .get(provider, {})
            .get("client_id")
        )
        provider_instance = adapter.get_provider(request, provider, client_id=client_id)

        base_url = provider_instance.get_login_url(request)
        query_params = {
            "next": build_absolute_uri("plugins:socialauth:social.oauth.return")
        }
        parsed_url = urlparse(base_url)
        updated_url = parsed_url._replace(query=urlencode(query_params))
        return redirect(urlunparse(updated_url))

    def set_oauth2_params(self, request: HttpRequest) -> None:
        """
        Handle Login with SSO button from other components
        This function will set 'oauth2_params' in session for oauth2_callback
        """
        next_url = request.GET.get("next", "")
        if next_url:
            parsed = urlparse(next_url)
            params = parse_qs(parsed.query)
            request.session["oauth2_params"] = {
                k: v[0] for k, v in params.items()
            }


class OAuthReturnView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        try:
            user = self.get_or_create_user(request)
            response = process_login_and_set_cookie(request, user, False)
            oauth2_params = request.session.get("oauth2_params", {})
            if oauth2_params:
                get_params = self.prepare_oauth2_params(oauth2_params)
                auth_url = reverse("control:oauth2_provider.authorize")

                # Clean up session after use
                del request.session["oauth2_params"]

                return redirect(f"{auth_url}?{get_params.urlencode()}")

            return response
        except AttributeError as e:
            messages.error(
                request, _("Error while authorizing: no email address available.")
            )
            logger.error("Error while authorizing: %s", e)
            return redirect("control:auth.login")

    def get_or_create_user(self, request: HttpRequest) -> User:
        """
        Get or create a user from social auth information.
        """
        return User.objects.get_or_create(
            email=request.user.email,
            defaults={
                "locale": getattr(request, "LANGUAGE_CODE", settings.LANGUAGE_CODE),
                "timezone": getattr(request, "timezone", settings.TIME_ZONE),
                "auth_backend": "native",
                "password": "",
            },
        )[0]

    def prepare_oauth2_params(self, oauth2_params: dict) -> QueryDict:
        """
        Prepare OAuth2 parameters to be passed to the OAuth2 authorization view.
        """
        get_params = QueryDict("", mutable=True)
        base_params = {
            "response_type": oauth2_params.get("response_type", "code"),
            "client_id": oauth2_params.get("client_id"),
            "redirect_uri": oauth2_params.get("redirect_uri"),
            "scope": oauth2_params.get("scope", "profile"),
            "state": oauth2_params.get("state"),
        }
        get_params.update(base_params)
        return get_params


class SocialLoginView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'socialauth/social_auth_settings.html'

    class SettingState(StrEnum):
        ENABLED = "enabled"
        DISABLED = "disabled"
        CREDENTIALS = "credentials"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gs = GlobalSettingsObject()
        self.set_initial_state()

    def set_initial_state(self):
        """
        Set the initial state of the login providers
        If the login providers are not valid, set them to the default
        """
        def validate_login_providers(login_providers):
            try:
                validated_providers = LoginProviders.model_validate(login_providers)
                return validated_providers
            except ValidationError as e:
                logger.error('Error while validating login providers: %s', e)
                return None

        login_providers = self.gs.settings.get('login_providers', as_type=dict)
        if login_providers is None or validate_login_providers(login_providers) is None:
            self.gs.settings.set('login_providers', LoginProviders().model_dump())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['login_providers'] = self.gs.settings.get('login_providers', as_type=dict)
        context['tickets_domain'] = urljoin(settings.SITE_URL, settings.BASE_PATH)
        return context

    def post(self, request, *args, **kwargs):
        login_providers = self.gs.settings.get('login_providers', as_type=dict)
        setting_state = request.POST.get('save_credentials', '').lower()

        for provider in LoginProviders.model_fields.keys():
            if setting_state == self.SettingState.CREDENTIALS:
                self.update_credentials(request, provider, login_providers)
            else:
                self.update_provider_state(request, provider, login_providers)

        self.gs.settings.set('login_providers', login_providers)
        return redirect(self.get_success_url())

    def update_credentials(self, request, provider, login_providers):
        client_id_value = request.POST.get(f'{provider}_client_id', '')
        secret_value = request.POST.get(f'{provider}_secret', '')

        if client_id_value and secret_value:
            login_providers[provider]['client_id'] = client_id_value
            login_providers[provider]['secret'] = secret_value

            SocialApp.objects.update_or_create(
                provider=provider,
                defaults={
                    'client_id': client_id_value,
                    'secret': secret_value,
                }
            )

    def update_provider_state(self, request, provider, login_providers):
        setting_state = request.POST.get(f'{provider}_login', '').lower()
        if setting_state in [s.value for s in self.SettingState]:
            login_providers[provider]['state'] = setting_state == self.SettingState.ENABLED

    def get_success_url(self) -> str:
        return reverse('plugins:socialauth:admin.global.social.auth.settings')
