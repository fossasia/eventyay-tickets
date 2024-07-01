import copy
import hashlib
import logging
import uuid
from datetime import datetime, timedelta

import requests
from django.core.cache import cache
from paypalcheckoutsdk.core import (
    AccessToken, PayPalHttpClient as VendorPayPalHttpClient,
)
from requests.adapters import HTTPAdapter
from urllib3 import Retry
from urllib3.exceptions import MaxRetryError

logger = logging.getLogger(__name__)


class LogOnRetry(Retry):
    def increment(self, method=None, url=None, response=None, error=None, _pool=None, _stacktrace=None) -> Retry:
        log_string = f'({method} {url}): {error if error else (response.status if response else "unknown")}'
        logger.warning(f'PayPal Retry called {log_string} after {len(self.history)} attempts')
        try:
            return super().increment(method, url, response, error, _pool, _stacktrace)
        except MaxRetryError:
            logger.error(f'PayPal Retry failed {log_string} after {len(self.history)} attempts')
            raise


class PayPalHttpClient(VendorPayPalHttpClient):
    """
    Custom HTTP client for interacting with PayPal APIs, extending from `VendorPayPalHttpClient`.
    Handles access token management, retries, and custom headers for PayPal API requests.

    Attributes:
        environment (Environment): The environment configuration for PayPal.
        session (requests.Session): HTTP session for making requests.
        _access_token (AccessToken): Cached access token for authentication.
    """

    def __init__(self, environment):
        """
        Initialize the PayPal HTTP client with the specified environment configuration.

        Args:
            environment (Environment): The environment configuration object.
        """
        super().__init__(environment)
        self.session = requests.Session()

        # Configure retry logic for HTTP requests
        retries = Retry(
            total=5,
            backoff_factor=0.05,
            status_forcelist=[404, 500, 502, 503, 504],
            allowed_methods=frozenset(["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "PATCH", "POST"]),
            raise_on_status=False,
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def __call__(self, request):
        """
        Handle the execution of an HTTP request, manage access token caching, and set custom headers.

        Args:
            request (requests.Request): The HTTP request object to be executed.
        """
        # Generate cache key for access token based on environment and increment
        checksum = hashlib.sha256(''.join([
            self.environment.base_url, self.environment.client_id, self.environment.client_secret
        ]).encode()).hexdigest()
        cache_key = f'paypal_access_token_{checksum}'

        # Retrieve access token from cache if available
        token_data = cache.get(cache_key)
        if token_data:
            expires_at = datetime.fromtimestamp(token_data['expires_at'])
            if expires_at > datetime.now():
                self._access_token = AccessToken(
                    access_token=token_data['access_token'],
                    expires_in=token_data['expires_in'],
                    token_type=token_data['token_type']
                )
                self._access_token.created_at = token_data['created_at']

        # Call superclass method to execute the request
        super().__call__(request)

        # Update cache with new access token if it has changed
        if self._access_token and (not token_data or token_data['access_token'] != self._access_token.access_token):
            expiration = self._access_token.expires_in - 60  # Cache token with a safety margin
            cache.set(cache_key, {
                'access_token': self._access_token.access_token,
                'expires_at': (datetime.now() + timedelta(seconds=self._access_token.expires_in)).timestamp(),
                'expires_in': self._access_token.expires_in,
                'token_type': self._access_token.token_type,
                'created_at': self._access_token.created_at
            }, expiration)

        # Set PayPal specific headers for the request
        if self.environment.merchant_id:
            request.headers["PayPal-Auth-Assertion"] = self.environment.authorization_assertion()

        if self.environment.partner_id:
            request.headers["PayPal-Partner-Attribution-Id"] = self.environment.partner_id

        if "PayPal-Request-Id" not in request.headers:
            request.headers["PayPal-Request-Id"] = str(uuid.uuid4())

    def _parse_csp(self, csp_header):
        # Implement CSP parsing logic if needed
        pass

    def _merge_csp(self, existing_csp, new_directives):
        # Implement CSP merging logic if needed
        pass

    def _render_csp(self, csp_directives):
        # Implement CSP rendering logic if needed
        pass

    def execute(self, request):
        req_cpy = copy.deepcopy(request)

        # Ensure reqCpy has headers attribute
        try:
            getattr(req_cpy, 'headers')
        except AttributeError:
            req_cpy.headers = {}

        # Apply any injectors (assuming _injectors is a list of functions)
        for injector in self._injectors:
            injector(req_cpy)

        data = None

        # Format headers
        formatted_headers = self.format_headers(req_cpy.headers)

        # Set default User-Agent if not provided
        if "user-agent" not in formatted_headers:
            req_cpy.headers["user-agent"] = self.get_user_agent()

        # Serialize request data if body exists
        if hasattr(req_cpy, 'body') and req_cpy.body is not None:
            raw_headers = req_cpy.headers
            req_cpy.headers = formatted_headers
            data = self.encoder.serialize_request(req_cpy)
            req_cpy.headers = self.map_headers(raw_headers, formatted_headers)

        # Make the HTTP request
        resp = self.session.request(
            method=req_cpy.verb,
            url=self.environment.base_url + req_cpy.path,
            headers=req_cpy.headers,
            data=data
        )

        # Parse and return the response
        return self.parse_response(resp)
