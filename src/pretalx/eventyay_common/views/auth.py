import logging
import os

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse
from requests_oauthlib import OAuth2Session

from pretalx.person.models import User

logger = logging.getLogger(__name__)


# Set the OAUTHLIB_INSECURE_TRANSPORT environment variable based on the setting
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = (
    "1" if settings.OAUTHLIB_INSECURE_TRANSPORT else "0"
)


def oauth2_login_view(request, *args, **kwargs):
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
    # Create an OAuth2 session using the client ID and redirect URI
    oauth2_session = OAuth2Session(
        client_id=sso_provider.client_id,
        redirect_uri=settings.OAUTH2_PROVIDER["REDIRECT_URI"],
        scope=settings.OAUTH2_PROVIDER["SCOPE"],
    )

    # Generate the authorization URL for the SSO provider
    authorization_url, state = oauth2_session.authorization_url(
        settings.OAUTH2_PROVIDER["AUTHORIZE_URL"]
    )

    # Save the OAuth2 session state to the user's session for security
    request.session["oauth2_state"] = state

    # Redirect to the SSO provider's login page
    return redirect(authorization_url)


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
    return redirect(reverse("cfp:root.main"))
