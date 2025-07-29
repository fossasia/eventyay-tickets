"""
Custom MediaWiki provider for django-allauth that implements proper rate limiting
to comply with Wikimedia API usage guidelines.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from allauth.socialaccount.providers.mediawiki.provider import MediaWikiProvider as BaseMediaWikiProvider
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class RateLimitedOAuth2Client(OAuth2Client):
    """
    OAuth2 client that implements proper rate limiting for Wikimedia APIs
    according to their usage guidelines.
    """
    
    RATE_LIMIT_KEY = "mediawiki_oauth_rate_limit"
    RATE_LIMIT_WINDOW = 60  # 1 minute window
    MAX_REQUESTS_PER_WINDOW = 50  # Conservative limit
    BACKOFF_BASE_DELAY = 1.0  # Base delay in seconds
    MAX_BACKOFF_DELAY = 60.0  # Maximum backoff delay
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with proper User-Agent and timeout settings."""
        session = requests.Session()
        
        # Set proper User-Agent as required by Wikimedia guidelines
        user_agent = getattr(settings, 'MEDIAWIKI_USER_AGENT', None)
        if not user_agent:
            # Fallback to a generic but compliant User-Agent
            user_agent = (
                f"EventyAY-Tickets/{getattr(settings, 'VERSION', '1.0')} "
                f"(https://eventyay.com; contact@eventyay.com) "
                f"django-allauth/{self._get_allauth_version()}"
            )
        
        session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'application/json',
        })
        
        return session
    
    def _get_allauth_version(self) -> str:
        """Get django-allauth version for User-Agent."""
        try:
            import allauth
            return getattr(allauth, '__version__', 'unknown')
        except ImportError:
            return 'unknown'
    
    def _check_rate_limit(self) -> bool:
        """
        Check if we're within rate limits. Returns True if we can proceed.
        Implements a sliding window rate limiter with atomic operations to prevent race conditions.
        
        Note: For high-concurrency deployments, it's recommended to use a cache backend
        that supports locking (e.g., Redis with Django 4.0+). The fallback for 
        non-locking backends has a slight race condition that may allow excess requests
        under extreme load, though this is better than blocking OAuth entirely.
        """
        now = time.time()
        window_start = now - self.RATE_LIMIT_WINDOW
        
        # Get current requests in the window
        requests_key = f"{self.RATE_LIMIT_KEY}:requests"
        lock_key = f"{requests_key}:lock"
        
        # Try to acquire lock for atomic operations
        try:
            # Use Django's cache framework lock if available (Django 4.0+)
            if hasattr(cache, 'lock'):
                with cache.lock(lock_key, timeout=5):
                    current_requests = cache.get(requests_key, [])
                    
                    # Filter out old requests outside the window
                    current_requests = [req_time for req_time in current_requests if req_time > window_start]
                    
                    # Check if we're within limits
                    if len(current_requests) >= self.MAX_REQUESTS_PER_WINDOW:
                        return False
                    
                    # Add current request timestamp
                    current_requests.append(now)
                    cache.set(requests_key, current_requests, self.RATE_LIMIT_WINDOW * 2)
                    
                    return True
            else:
                # Fallback for cache backends without locking support
                # This has a slight race condition but is better than crashing
                current_requests = cache.get(requests_key, [])
                
                # Filter out old requests outside the window
                current_requests = [req_time for req_time in current_requests if req_time > window_start]
                
                # Check if we're within limits
                if len(current_requests) >= self.MAX_REQUESTS_PER_WINDOW:
                    return False
                
                # Add current request timestamp
                current_requests.append(now)
                cache.set(requests_key, current_requests, self.RATE_LIMIT_WINDOW * 2)
                
                return True
                
        except Exception as e:
            # If cache operations fail, log and allow the request to proceed
            # This prevents cache failures from breaking OAuth entirely
            logger.warning(f"Rate limit check failed due to cache error: {e}")
            return True
    
    def _get_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = min(
            self.BACKOFF_BASE_DELAY * (2 ** attempt),
            self.MAX_BACKOFF_DELAY
        )
        return delay
    
    def _wait_for_rate_limit(self, attempt: int = 0) -> None:
        """Wait with exponential backoff if rate limited."""
        delay = self._get_backoff_delay(attempt)
        logger.warning(
            f"MediaWiki OAuth rate limited, waiting {delay:.2f} seconds (attempt {attempt + 1})"
        )
        time.sleep(delay)
    
    def _make_request_with_retries(self, method: str, url: str, max_retries: int = 3, **kwargs) -> requests.Response:
        """
        Make HTTP request with rate limiting and retry logic.
        """
        # Set reasonable timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30
            
        for attempt in range(max_retries + 1):
            # Check rate limit before making request
            if not self._check_rate_limit():
                if attempt < max_retries:
                    self._wait_for_rate_limit(attempt)
                    continue
                else:
                    raise Exception("MediaWiki OAuth rate limit exceeded after maximum retries")
            
            try:
                response = self.session.request(method, url, **kwargs)
                
                # Check for rate limiting response
                if response.status_code == 429:  # Too Many Requests
                    if attempt < max_retries:
                        # Check for Retry-After header
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                delay = float(retry_after)
                                logger.warning(f"MediaWiki API returned 429, waiting {delay} seconds")
                                time.sleep(delay)
                                continue
                            except ValueError:
                                pass
                        
                        self._wait_for_rate_limit(attempt)
                        continue
                    else:
                        raise Exception("MediaWiki OAuth rate limited (HTTP 429) after maximum retries")
                
                # Check for other server errors that might indicate throttling
                if response.status_code >= 500:
                    if attempt < max_retries:
                        logger.warning(f"MediaWiki API server error {response.status_code}, retrying...")
                        self._wait_for_rate_limit(attempt)
                        continue
                    else:
                        response.raise_for_status()
                
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    logger.warning(f"MediaWiki OAuth request failed: {e}, retrying...")
                    self._wait_for_rate_limit(attempt)
                    continue
                else:
                    raise
        
        raise Exception("Maximum retries exceeded for MediaWiki OAuth request")
    
    def get_access_token(self, code, redirect_uri):
        """Override to use rate-limited requests."""
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.consumer_key,
            'client_secret': self.consumer_secret,
            'redirect_uri': redirect_uri,
            'code': code,
        }
        
        response = self._make_request_with_retries(
            'POST',
            self.access_token_url,
            data=data,
            headers={'Accept': 'application/json'}
        )
        
        try:
            return response.json()
        except ValueError:
            # Response was not JSON, or decoding failed
            raise Exception(
                f"Failed to decode JSON from MediaWiki API response: {response.text[:200]}"
            )
    
    def get_user_info(self, access_token):
        """Override to use rate-limited requests for user info."""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        }
        
        response = self._make_request_with_retries(
            'GET',
            'https://meta.wikimedia.org/w/api.php',
            params={
                'action': 'query',
                'meta': 'userinfo',
                'uiprop': 'email|realname',
                'format': 'json'
            },
            headers=headers
        )
        
        try:
            return response.json()
        except ValueError:
            # Response was not JSON, or decoding failed
            raise Exception(
                f"Failed to decode JSON from MediaWiki API response: {response.text[:200]}"
            )


class MediaWikiProvider(BaseMediaWikiProvider):
    """
    Custom MediaWiki provider that uses rate-limited OAuth2 client.
    """
    
    def get_oauth2_client_class(self):
        """Return our custom rate-limited OAuth2 client."""
        return RateLimitedOAuth2Client
