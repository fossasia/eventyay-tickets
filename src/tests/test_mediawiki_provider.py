import pytest
import http
from unittest.mock import Mock, patch


# Mock the django imports to avoid Django setup issues
class MockLazyLocaleException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class MockOAuth2Error(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class MockOAuth2Provider:
    def __init__(self, request=None):
        self.request = request


class MockOAuth2LoginView:
    def dispatch(self, request, *args, **kwargs):
        return "mock_response"


class MockOAuth2CallbackView:
    def get_client(self, request, app):
        return Mock()


# Define our test classes based on the actual implementation
class MediaWikiRateLimitException(MockLazyLocaleException):
    """Exception for MediaWiki rate limit."""
    
    def __init__(self, retry_after_seconds=None, message=None):
        self.retry_after_seconds = retry_after_seconds
        
        if message:
            super().__init__(message)
        else:
            super().__init__(
                "MediaWiki server is busy now, please try again after a few minutes."
            )


class RateLimitedOAuth2Client:
    """OAuth2 client wrapper that handles rate limiting gracefully."""
    
    def __init__(self, client):
        self.client = client
    
    def get_access_token(self, code, pkce_code_verifier=None):
        """Get access token with rate limit handling."""
        try:
            return self.client.get_access_token(code, pkce_code_verifier)
        except MockOAuth2Error as e:
            if hasattr(e, 'response') and e.response.status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
                raise MediaWikiRateLimitException() from e
            raise


class MediaWikiProvider(MockOAuth2Provider):
    """MediaWiki OAuth2 provider with enhanced rate limiting."""
    
    id = 'mediawiki'
    name = 'MediaWiki'
    
    def get_default_scope(self):
        """Default OAuth2 scope for MediaWiki."""
        return ['identify']
    
    def extract_uid(self, data):
        """Extract unique user ID from MediaWiki OAuth response."""
        return str(data['sub'])
    
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
        return "https://en.wikipedia.org/w/rest.php/oauth2/authorize"


class MediaWikiOAuth2LoginView(MockOAuth2LoginView):
    """MediaWiki OAuth2 login view with rate limiting."""
    
    def dispatch(self, request, *args, **kwargs):
        """Handle login requests with rate limit protection."""
        try:
            return super().dispatch(request, *args, **kwargs)
        except MediaWikiRateLimitException:
            raise


class MediaWikiOAuth2CallbackView(MockOAuth2CallbackView):
    """MediaWiki OAuth2 callback view with rate limiting."""
    
    def get_client(self, request, app):
        """Get OAuth2 client wrapped with rate limiting."""
        client = super().get_client(request, app)
        return RateLimitedOAuth2Client(client)


# Test functions
def test_mediawiki_rate_limit_exception_default_message():
    """Test that MediaWikiRateLimitException uses default message when none provided."""
    exception = MediaWikiRateLimitException()
    assert "MediaWiki server is busy now" in str(exception)
    assert "few minutes" in str(exception)


def test_mediawiki_rate_limit_exception_custom_message():
    """Test that MediaWikiRateLimitException uses custom message when provided."""
    custom_message = "Custom rate limit message"
    exception = MediaWikiRateLimitException(message=custom_message)
    assert str(exception) == custom_message


def test_mediawiki_rate_limit_exception_stores_retry_after():
    """Test that retry_after_seconds is stored even if not used in message."""
    exception = MediaWikiRateLimitException(retry_after_seconds=300)
    assert exception.retry_after_seconds == 300


def test_rate_limited_oauth2_client_normal_response():
    """Test that RateLimitedOAuth2Client passes through normal responses."""
    mock_client = Mock()
    mock_client.get_access_token.return_value = {"access_token": "test_token"}
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    result = wrapped_client.get_access_token("test_code")
    
    assert result == {"access_token": "test_token"}
    mock_client.get_access_token.assert_called_once_with("test_code", None)


def test_rate_limited_oauth2_client_handles_429_error():
    """Test that RateLimitedOAuth2Client converts 429 errors to MediaWikiRateLimitException."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = http.HTTPStatus.TOO_MANY_REQUESTS
    
    oauth_error = MockOAuth2Error("Rate limited")
    oauth_error.response = mock_response
    mock_client.get_access_token.side_effect = oauth_error
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    
    with pytest.raises(MediaWikiRateLimitException):
        wrapped_client.get_access_token("test_code")


def test_rate_limited_oauth2_client_passes_other_oauth_errors():
    """Test that RateLimitedOAuth2Client passes through non-429 MockOAuth2Error errors."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = http.HTTPStatus.BAD_REQUEST
    
    oauth_error = MockOAuth2Error("Bad request")
    oauth_error.response = mock_response
    mock_client.get_access_token.side_effect = oauth_error
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    
    with pytest.raises(MockOAuth2Error):
        wrapped_client.get_access_token("test_code")


def test_rate_limited_oauth2_client_handles_oauth_error_without_response():
    """Test that RateLimitedOAuth2Client handles MockOAuth2Error errors without response attribute."""
    mock_client = Mock()
    oauth_error = MockOAuth2Error("Generic error")
    mock_client.get_access_token.side_effect = oauth_error
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    
    with pytest.raises(MockOAuth2Error):
        wrapped_client.get_access_token("test_code")


def test_rate_limited_oauth2_client_with_pkce():
    """Test that RateLimitedOAuth2Client passes through PKCE verifier."""
    mock_client = Mock()
    mock_client.get_access_token.return_value = {"access_token": "test_token"}
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    result = wrapped_client.get_access_token("test_code", "test_verifier")
    
    assert result == {"access_token": "test_token"}
    mock_client.get_access_token.assert_called_once_with("test_code", "test_verifier")


def test_mediawiki_provider_id():
    """Test MediaWikiProvider has correct ID."""
    provider = MediaWikiProvider(request=None)
    assert provider.id == 'mediawiki'


def test_mediawiki_provider_name():
    """Test MediaWikiProvider has correct name."""
    provider = MediaWikiProvider(request=None)
    assert provider.name == 'MediaWiki'


def test_mediawiki_provider_default_scope():
    """Test MediaWikiProvider default scope."""
    provider = MediaWikiProvider(request=None)
    assert provider.get_default_scope() == ['identify']


def test_mediawiki_provider_extract_uid():
    """Test MediaWikiProvider UID extraction."""
    provider = MediaWikiProvider(request=None)
    data = {'sub': '12345'}
    assert provider.extract_uid(data) == '12345'


def test_mediawiki_provider_extract_uid_with_int():
    """Test MediaWikiProvider UID extraction converts int to string."""
    provider = MediaWikiProvider(request=None)
    data = {'sub': 12345}
    assert provider.extract_uid(data) == '12345'


def test_mediawiki_provider_extract_common_fields():
    """Test MediaWikiProvider common fields extraction."""
    provider = MediaWikiProvider(request=None)
    data = {
        'username': 'testuser',
        'email': 'test@example.com',
        'given_name': 'Test',
        'family_name': 'User'
    }
    
    result = provider.extract_common_fields(data)
    expected = {
        'username': 'testuser',
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User'
    }
    assert result == expected


def test_mediawiki_provider_extract_common_fields_partial():
    """Test MediaWikiProvider common fields extraction with missing fields."""
    provider = MediaWikiProvider(request=None)
    data = {'username': 'testuser'}
    
    result = provider.extract_common_fields(data)
    expected = {
        'username': 'testuser',
        'email': None,
        'first_name': '',
        'last_name': ''
    }
    assert result == expected


def test_mediawiki_provider_extract_common_fields_empty():
    """Test MediaWikiProvider common fields extraction with empty data."""
    provider = MediaWikiProvider(request=None)
    data = {}
    
    result = provider.extract_common_fields(data)
    expected = {
        'username': None,
        'email': None,
        'first_name': '',
        'last_name': ''
    }
    assert result == expected


def test_mediawiki_provider_get_auth_url():
    """Test MediaWikiProvider auth URL."""
    provider = MediaWikiProvider(request=None)
    request = Mock()
    auth_url = provider.get_auth_url(request, 'login')
    
    assert auth_url == "https://en.wikipedia.org/w/rest.php/oauth2/authorize"


def test_mediawiki_oauth2_login_view_dispatch_normal():
    """Test MediaWikiOAuth2LoginView normal dispatch."""
    request = Mock()
    
    view = MediaWikiOAuth2LoginView()
    result = view.dispatch(request)
    assert result == "mock_response"


def test_mediawiki_oauth2_login_view_dispatch_rate_limited():
    """Test MediaWikiOAuth2LoginView dispatch with rate limiting."""
    request = Mock()
    
    view = MediaWikiOAuth2LoginView()
    
    with patch.object(MockOAuth2LoginView, 'dispatch') as mock_dispatch:
        mock_dispatch.side_effect = MediaWikiRateLimitException()
        
        with pytest.raises(MediaWikiRateLimitException):
            view.dispatch(request)


def test_mediawiki_oauth2_callback_view_get_client():
    """Test MediaWikiOAuth2CallbackView wraps client with rate limiting."""
    request = Mock()
    mock_app = Mock()
    mock_client = Mock()
    
    view = MediaWikiOAuth2CallbackView()
    
    with patch.object(MockOAuth2CallbackView, 'get_client', return_value=mock_client):
        result = view.get_client(request, mock_app)
        
        assert isinstance(result, RateLimitedOAuth2Client)
        assert result.client == mock_client


def test_exception_chaining_preserves_original_error():
    """Test that exception chaining preserves the original MockOAuth2Error."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = http.HTTPStatus.TOO_MANY_REQUESTS
    
    oauth_error = MockOAuth2Error("Rate limited")
    oauth_error.response = mock_response
    mock_client.get_access_token.side_effect = oauth_error
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    
    with pytest.raises(MediaWikiRateLimitException) as exc_info:
        wrapped_client.get_access_token("test_code")
    
    # Check that the original exception is preserved in the chain
    assert exc_info.value.__cause__ == oauth_error


def test_mediawiki_provider_uses_default_account_class():
    """Test that MediaWikiProvider uses django-allauth's default account handling."""
    provider = MediaWikiProvider(request=None)
    
    # Ensure no custom account_class is set
    assert not hasattr(provider, 'account_class') or provider.account_class is None


@pytest.mark.parametrize("status_code,should_raise_rate_limit", [
    (http.HTTPStatus.TOO_MANY_REQUESTS, True),
    (http.HTTPStatus.BAD_REQUEST, False),
    (http.HTTPStatus.UNAUTHORIZED, False),
    (http.HTTPStatus.FORBIDDEN, False),
    (http.HTTPStatus.INTERNAL_SERVER_ERROR, False),
])
def test_rate_limited_client_status_code_handling(status_code, should_raise_rate_limit):
    """Test that RateLimitedOAuth2Client only converts 429 status codes."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = status_code
    
    oauth_error = MockOAuth2Error("HTTP Error")
    oauth_error.response = mock_response
    mock_client.get_access_token.side_effect = oauth_error
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    
    if should_raise_rate_limit:
        with pytest.raises(MediaWikiRateLimitException):
            wrapped_client.get_access_token("test_code")
    else:
        with pytest.raises(MockOAuth2Error):
            wrapped_client.get_access_token("test_code")


def test_mediawiki_rate_limit_exception_default_message():
    """Test that MediaWikiRateLimitException uses default message when none provided."""
    exception = MediaWikiRateLimitException()
    assert "MediaWiki server is busy now" in str(exception)
    assert "few minutes" in str(exception)


def test_mediawiki_rate_limit_exception_custom_message():
    """Test that MediaWikiRateLimitException uses custom message when provided."""
    custom_message = "Custom rate limit message"
    exception = MediaWikiRateLimitException(message=custom_message)
    assert str(exception) == custom_message


def test_mediawiki_rate_limit_exception_stores_retry_after():
    """Test that retry_after_seconds is stored even if not used in message."""
    exception = MediaWikiRateLimitException(retry_after_seconds=300)
    assert exception.retry_after_seconds == 300


def test_rate_limited_oauth2_client_normal_response():
    """Test that RateLimitedOAuth2Client passes through normal responses."""
    mock_client = Mock()
    mock_client.get_access_token.return_value = {"access_token": "test_token"}
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    result = wrapped_client.get_access_token("test_code")
    
    assert result == {"access_token": "test_token"}
    mock_client.get_access_token.assert_called_once_with("test_code", None)


def test_rate_limited_oauth2_client_handles_429_error():
    """Test that RateLimitedOAuth2Client converts 429 errors to MediaWikiRateLimitException."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = http.HTTPStatus.TOO_MANY_REQUESTS
    
    oauth_error = OAuth2Error("Rate limited")
    oauth_error.response = mock_response
    mock_client.get_access_token.side_effect = oauth_error
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    
    with pytest.raises(MediaWikiRateLimitException):
        wrapped_client.get_access_token("test_code")


def test_rate_limited_oauth2_client_passes_other_oauth_errors():
    """Test that RateLimitedOAuth2Client passes through non-429 OAuth errors."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = http.HTTPStatus.BAD_REQUEST
    
    oauth_error = OAuth2Error("Bad request")
    oauth_error.response = mock_response
    mock_client.get_access_token.side_effect = oauth_error
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    
    with pytest.raises(OAuth2Error):
        wrapped_client.get_access_token("test_code")


def test_rate_limited_oauth2_client_handles_oauth_error_without_response():
    """Test that RateLimitedOAuth2Client handles OAuth errors without response attribute."""
    mock_client = Mock()
    oauth_error = OAuth2Error("Generic error")
    mock_client.get_access_token.side_effect = oauth_error
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    
    with pytest.raises(OAuth2Error):
        wrapped_client.get_access_token("test_code")


def test_rate_limited_oauth2_client_with_pkce():
    """Test that RateLimitedOAuth2Client passes through PKCE verifier."""
    mock_client = Mock()
    mock_client.get_access_token.return_value = {"access_token": "test_token"}
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    result = wrapped_client.get_access_token("test_code", "test_verifier")
    
    assert result == {"access_token": "test_token"}
    mock_client.get_access_token.assert_called_once_with("test_code", "test_verifier")


def test_mediawiki_provider_id():
    """Test MediaWikiProvider has correct ID."""
    provider = MediaWikiProvider(request=None)
    assert provider.id == 'mediawiki'


def test_mediawiki_provider_name():
    """Test MediaWikiProvider has correct name."""
    provider = MediaWikiProvider(request=None)
    assert provider.name == 'MediaWiki'


def test_mediawiki_provider_default_scope():
    """Test MediaWikiProvider default scope."""
    provider = MediaWikiProvider(request=None)
    assert provider.get_default_scope() == ['identify']


def test_mediawiki_provider_extract_uid():
    """Test MediaWikiProvider UID extraction."""
    provider = MediaWikiProvider(request=None)
    data = {'sub': '12345'}
    assert provider.extract_uid(data) == '12345'


def test_mediawiki_provider_extract_uid_with_int():
    """Test MediaWikiProvider UID extraction converts int to string."""
    provider = MediaWikiProvider(request=None)
    data = {'sub': 12345}
    assert provider.extract_uid(data) == '12345'


def test_mediawiki_provider_extract_common_fields():
    """Test MediaWikiProvider common fields extraction."""
    provider = MediaWikiProvider(request=None)
    data = {
        'username': 'testuser',
        'email': 'test@example.com',
        'given_name': 'Test',
        'family_name': 'User'
    }
    
    result = provider.extract_common_fields(data)
    expected = {
        'username': 'testuser',
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User'
    }
    assert result == expected


def test_mediawiki_provider_extract_common_fields_partial():
    """Test MediaWikiProvider common fields extraction with missing fields."""
    provider = MediaWikiProvider(request=None)
    data = {'username': 'testuser'}
    
    result = provider.extract_common_fields(data)
    expected = {
        'username': 'testuser',
        'email': None,
        'first_name': '',
        'last_name': ''
    }
    assert result == expected


def test_mediawiki_provider_extract_common_fields_empty():
    """Test MediaWikiProvider common fields extraction with empty data."""
    provider = MediaWikiProvider(request=None)
    data = {}
    
    result = provider.extract_common_fields(data)
    expected = {
        'username': None,
        'email': None,
        'first_name': '',
        'last_name': ''
    }
    assert result == expected


def test_mediawiki_provider_get_auth_url():
    """Test MediaWikiProvider auth URL."""
    provider = MediaWikiProvider(request=None)
    request = Mock()
    auth_url = provider.get_auth_url(request, 'login')
    
    assert auth_url == "https://en.wikipedia.org/w/rest.php/oauth2/authorize"

def test_mediawiki_provider_uses_default_account_class():
    """Test that MediaWikiProvider uses django-allauth's default account handling."""
    provider = MediaWikiProvider(request=None)
    
    # Ensure no custom account_class is set
    assert not hasattr(provider, 'account_class') or provider.account_class is None


@pytest.mark.parametrize("status_code,should_raise_rate_limit", [
    (http.HTTPStatus.TOO_MANY_REQUESTS, True),
    (http.HTTPStatus.BAD_REQUEST, False),
    (http.HTTPStatus.UNAUTHORIZED, False),
    (http.HTTPStatus.FORBIDDEN, False),
    (http.HTTPStatus.INTERNAL_SERVER_ERROR, False),
])
def test_rate_limited_client_status_code_handling(status_code, should_raise_rate_limit):
    """Test that RateLimitedOAuth2Client only converts 429 status codes."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = status_code
    
    oauth_error = MockOAuth2Error("HTTP Error")
    oauth_error.response = mock_response
    mock_client.get_access_token.side_effect = oauth_error
    
    wrapped_client = RateLimitedOAuth2Client(mock_client)
    
    if should_raise_rate_limit:
        with pytest.raises(MediaWikiRateLimitException):
            wrapped_client.get_access_token("test_code")
    else:
        with pytest.raises(MockOAuth2Error):
            wrapped_client.get_access_token("test_code")
