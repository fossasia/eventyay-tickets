import logging
import os
from typing import Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from requests_oauthlib import OAuth2Session

from pretalx.person.models import User

logger = logging.getLogger(__name__)


# Set the OAUTHLIB_INSECURE_TRANSPORT environment variable based on the setting
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = (
    "1" if settings.OAUTHLIB_INSECURE_TRANSPORT else "0"
)


def validate_relative_url(next_url: str) -> bool:
    """
    Only allow relative urls
    """
    parsed = urlparse(next_url)
    if parsed.scheme or parsed.netloc:
        return False

    return True


def register(request: HttpRequest) -> HttpResponse:
    """
    Register a new user account and redirect to the previous page.

    This function constructs a registration URL with a 'next' parameter
    to ensure the user is redirected back to their original location
    after registration.
    """
    register_url = urljoin(settings.EVENTYAY_TICKET_BASE_PATH, "/control/register")
    next_url = request.GET.get("next") or request.POST.get("next")
    if next_url and validate_relative_url(next_url):
        full_next_url = request.build_absolute_uri(next_url)
        next_param = f"?next={quote(full_next_url)}"
        return redirect(f"{register_url}{next_param}")

    return redirect(register_url)


class OAuth2LoginView(View):
    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        # Store the 'next' URL in the session, for redirecting user back after login
        next_url = request.GET.get("next") or request.POST.get("next")
        if next_url and validate_relative_url(next_url):
            request.session["next"] = next_url

        sso_provider = self.get_sso_provider()
        if not sso_provider:
            return self.handle_sso_not_configured(request)
        oauth2_session = self.create_oauth2_session(sso_provider)
        authorization_url, state = self.get_authorization_url(oauth2_session)
        request.session["oauth2_state"] = state

        return redirect(authorization_url)

    @staticmethod
    def get_sso_provider() -> Optional[SocialApp]:
        return SocialApp.objects.filter(provider=settings.EVENTYAY_SSO_PROVIDER).first()

    @staticmethod
    def handle_sso_not_configured(request: HttpRequest) -> HttpResponse:
        messages.error(
            request,
            "SSO not configured yet, please contact the "
            "administrator or come back later.",
        )
        return redirect(reverse("orga:login"))

    @staticmethod
    def create_oauth2_session(sso_provider: SocialApp) -> OAuth2Session:
        return OAuth2Session(
            client_id=sso_provider.client_id,
            redirect_uri=settings.OAUTH2_PROVIDER["REDIRECT_URI"],
            scope=settings.OAUTH2_PROVIDER["SCOPE"],
        )

    @staticmethod
    def get_authorization_url(oauth2_session: OAuth2Session) -> Tuple[str, str]:
        return oauth2_session.authorization_url(
            settings.OAUTH2_PROVIDER["AUTHORIZE_URL"]
        )


def oauth2_callback(request):
    sso_provider = SocialApp.objects.filter(
        provider=settings.EVENTYAY_SSO_PROVIDER
    ).first()
    if not sso_provider:
        messages.error(
            request,
            "SSO not configured yet, please contact the "
            "administrator or come back later.",
        )
        return redirect(reverse("orga:login"))
    oauth2_session = OAuth2Session(
        sso_provider.client_id,
        redirect_uri=settings.OAUTH2_PROVIDER["REDIRECT_URI"],
        state=request.session.get("oauth2_state"),
    )

    try:
        # Fetch the token using the authorization code
        oauth2_session.fetch_token(
            settings.OAUTH2_PROVIDER["ACCESS_TOKEN_URL"],
            client_secret=sso_provider.secret,
            authorization_response=request.build_absolute_uri(),
            scope=settings.OAUTH2_PROVIDER["SCOPE"],
        )

        # Use the token to fetch user info from the SSO provider
        user_info = oauth2_session.get(settings.SSO_USER_INFO).json()

    except Exception as e:
        # Log the error for debugging
        logger.error(f"OAuth2 callback error: {e}")
        # Redirect to an error page
        return redirect(settings.LOGIN_REDIRECT_URL)

    # Proceed with user creation or login
    user, created = User.objects.get_or_create(email=user_info["email"])
    if created:
        user.set_unusable_password()
    user.name = user_info.get("name", "")
    user.is_active = True
    user.is_staff = user_info.get("is_staff", False)
    user.locale = user_info.get("locale", None)
    user.timezone = user_info.get("timezone", None)
    user.save()

    # Log the user into the session
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    # If a 'next' URL was stored in the session, use it for redirecting user back after login
    next_url = request.session.pop("next", None)
    if next_url and validate_relative_url(next_url):
        return redirect(next_url)
    return redirect(reverse("cfp:root.main"))
