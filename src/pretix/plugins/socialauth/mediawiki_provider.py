"""
Custom MediaWiki OAuth provider with user-friendly rate limiting.

This module implements MediaWiki OAuth authentication with proper rate limiting
handling that shows user-friendly time descriptions instead of exact retry times.
Addresses issue #817 by removing aggressive retry behavior and providing
gentle guidance to users when rate limited.
"""

import requests
from django.utils.translation import gettext_lazy as _
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from pretix.base.models import LazyLocaleException
from django.conf import settings
import platform
import requests as requests_lib


class MediaWikiRateLimitException(LazyLocaleException):
    """
    Exception raised when MediaWiki API rate limiting is encountered.
    
    Uses user-friendly time descriptions instead of exact retry times
    to avoid rushing users and provide a better experience.
    """
    
    def __init__(self, message=None, context=None):
        if message is None:
            message = _(
                "We're currently experiencing high traffic with Wikipedia login. "
                "Please try again in a few minutes."
            )
        
        if context is None:
            context = {}
            
        # Extract retry_after for internal tracking but don't expose exact time
        self.retry_after = context.get('retry_after')
        
        super().__init__(message, context)


class RateLimitedOAuth2Client(OAuth2Client):
    """
    OAuth2 client that handles MediaWiki API rate limiting gracefully.
    
    Instead of retrying automatically, it raises a user-friendly exception
    with vague time descriptions when rate limited.
    """
    
    def _get_user_agent(self):
        """
        Generate User-Agent string following Wikimedia guidelines.
        
        Format: AppName/Version (Contact) Library/Version
        """
        if hasattr(settings, 'MEDIAWIKI_USER_AGENT') and settings.MEDIAWIKI_USER_AGENT:
            return settings.MEDIAWIKI_USER_AGENT
            
        # Auto-generate following Wikimedia conventions
        app_name = "eventyay-tickets"
        version = "1.0"
        contact = "https://github.com/fossasia/eventyay-tickets"
        library = f"requests/{requests_lib.__version__}"
        python_version = platform.python_version()
        
        return f"{app_name}/{version} ({contact}) {library} Python/{python_version}"
    
    def _get_friendly_time_description(self, retry_after_seconds):
        """
        Convert retry time to user-friendly vague description.
        
        Args:
            retry_after_seconds: Number of seconds to retry after
            
        Returns:
            str: User-friendly time description
        """
        if retry_after_seconds is None:
            return "a few minutes"
        
        try:
            seconds = int(retry_after_seconds)
            if seconds <= 60:
                return "a minute"
            elif seconds <= 120:
                return "a couple of minutes"  
            elif seconds <= 300:
                return "a few minutes"
            elif seconds <= 600:
                return "several minutes"
            else:
                return "some time"
        except (ValueError, TypeError):
            return "a few minutes"
    
    def _handle_rate_limit_response(self, response):
        """
        Handle rate limit responses with user-friendly messaging.
        
        Args:
            response: HTTP response object with 429 status
            
        Raises:
            MediaWikiRateLimitException: With user-friendly time description
        """
        retry_after = None
        
        # Try to get retry-after header for internal tracking
        if 'retry-after' in response.headers:
            try:
                retry_after = int(response.headers['retry-after'])
            except (ValueError, TypeError):
                pass
        
        # Get user-friendly description (always vague)
        time_desc = self._get_friendly_time_description(retry_after)
        
        message = _(
            "Wikipedia login is temporarily busy. "
            "Please try again in {time_desc}."
        )
        
        context = {
            'time_desc': time_desc,
            'retry_after': retry_after
        }
        
        raise MediaWikiRateLimitException(message, context)
    
    def request(self, method, url, **kwargs):
        """
        Make HTTP request with proper rate limiting handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional request parameters
            
        Returns:
            Response object
            
        Raises:
            MediaWikiRateLimitException: When rate limited (429 response)
        """
        # Set custom User-Agent
        headers = kwargs.get('headers', {})
        headers['User-Agent'] = self._get_user_agent()
        kwargs['headers'] = headers
        
        # Make the request
        response = super().request(method, url, **kwargs)
        
        # Handle rate limiting - no retries, just friendly error
        if response.status_code == 429:
            self._handle_rate_limit_response(response)
        
        return response


try:
    from allauth.socialaccount.providers.mediawiki.provider import MediaWikiProvider as BaseMediaWikiProvider
    
    class MediaWikiProvider(BaseMediaWikiProvider):
        """
        Custom MediaWiki provider with user-friendly rate limiting.
        
        Extends the base MediaWiki provider to use our custom OAuth2 client
        that provides better rate limiting UX.
        """
        
        def get_oauth2_client_class(self):
            """Return our custom OAuth2 client class."""
            return RateLimitedOAuth2Client
            
except ImportError:
    # Fallback if base provider is not available
    class MediaWikiProvider:
        """Fallback MediaWiki provider for testing."""
        pass
