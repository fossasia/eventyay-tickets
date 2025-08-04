import logging
import http
from django.utils.translation import gettext_lazy as _
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from allauth.socialaccount.providers.oauth2.views import OAuth2LoginView, OAuth2CallbackView
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider
from pretix.base.i18n import LazyLocaleException

logger = logging.getLogger(__name__)


class MediaWikiRateLimitException(LazyLocaleException):
    """
    exception for MediaWiki rate limit.

    Simple, consistent message without specific time estimates
    """
    
    def __init__(self, retry_after_seconds=None, message=None):
        self.retry_after_seconds = retry_after_seconds
        
        if message:
            super().__init__(message)
        else:
            super().__init__(
                _("MediaWiki server is busy now, please try again after a few minutes.")
            )


class RateLimitedOAuth2Client:
    """
    OAuth2 client wrapper that handles rate limiting gracefully.
    
    Wraps the standard OAuth2 client to detect 429 responses and convert
    them to user-friendly exceptions without retry logic.
    """
    
    def __init__(self, client):
        self.client = client
    
    def get_access_token(self, code, pkce_code_verifier=None):
        """
        Get access token with rate limit handling.
        
        Makes the OAuth2 request and converts any 429 responses to
        user-friendly MediaWikiRateLimitException.
        """
        try:
            return self.client.get_access_token(code, pkce_code_verifier)
        except OAuth2Error as e:
            if hasattr(e, 'response') and e.response.status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
                logger.warning("MediaWiki OAuth rate limit hit, returning user-friendly error.")
                raise MediaWikiRateLimitException() from e
            raise


class MediaWikiProvider(OAuth2Provider):
    """
    MediaWiki OAuth2 provider with enhanced rate limiting.
    
    Provides OAuth2 authentication for MediaWiki instances with user-friendly
    rate limiting that gives helpful guidance without specific retry times.
    """
    
    id = 'mediawiki'
    name = 'MediaWiki'
    
    def get_default_scope(self):
        """Default OAuth2 scope for MediaWiki."""
        return ['identify']
    
    def extract_uid(self, data):
        """Extract unique user ID from MediaWiki OAuth response."""
        return str(data['sub'])  # MediaWiki OAuth uses 'sub' for user ID
    
    def extract_common_fields(self, data):
        """Extract common user fields from MediaWiki OAuth response."""
        return {
            'username': data.get('username'),
            'email': data.get('email'),
            'first_name': data.get('given_name', ''),
            'last_name': data.get('family_name', ''),
        }
    
    def get_auth_url(self, request, action):
        """Get the authorization URL for MediaWiki OAuth."""
        # This would be implemented based on the specific MediaWiki instance
        # For now, returning a placeholder
        return "https://en.wikipedia.org/w/rest.php/oauth2/authorize"


class MediaWikiOAuth2LoginView(OAuth2LoginView):
    """MediaWiki OAuth2 login view with rate limiting."""
    
    def dispatch(self, request, *args, **kwargs):
        """Handle login requests with rate limit protection."""
        try:
            return super().dispatch(request, *args, **kwargs)
        except MediaWikiRateLimitException:
            # Re-raise to be handled by the main error handler
            raise


class MediaWikiOAuth2CallbackView(OAuth2CallbackView):
    """MediaWiki OAuth2 callback view with rate limiting."""
    
    def get_client(self, request, app):
        """Get OAuth2 client wrapped with rate limiting."""
        client = super().get_client(request, app)
        return RateLimitedOAuth2Client(client)


# Provider configuration
provider_classes = [MediaWikiProvider]
