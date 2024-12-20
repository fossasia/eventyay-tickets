import logging
from enum import Enum
from urllib.parse import urlencode, urlparse, urlunparse

from allauth.socialaccount.adapter import get_adapter
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from pretix.base.models import User
from pretix.base.settings import GlobalSettingsObject
from pretix.control.permissions import AdministratorPermissionRequiredMixin
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


class LoginState(Enum):
    ENABLE = "enable"
    DISABLE = "disable"


class SocialLoginView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'socialauth/social_auth_settings.html'
    LOGIN_PROVIDERS = {'mediawiki': False, 'github': False, 'google': False}
    VALID_STATES = {'enable', 'disable'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gs = GlobalSettingsObject()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.gs.settings.get('login_providers', as_type=dict) is None:
            self.gs.settings.set('login_providers', self.LOGIN_PROVIDERS)
        context['login_providers'] = self.gs.settings.get('login_providers', as_type=dict)
        return context

    def post(self, request, *args, **kwargs):
        login_providers = self.gs.settings.get('login_providers', as_type=dict)
        for provider in self.LOGIN_PROVIDERS.keys():
            value = request.POST.get(f'{provider}_login', '').lower()
            if value not in [s.value for s in LoginState]:
                continue
            login_providers[provider] = value == LoginState.ENABLE.value
        self.gs.settings.set('login_providers', login_providers)
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        return reverse('plugins:socialauth:admin.global.social.auth.settings')
