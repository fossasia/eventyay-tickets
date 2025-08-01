"""
Tests for MediaWiki OAuth implementation with proper rate limiting.
Fixes issue #817: Remove retry logic for 429 errors and add proper User-Agent
"""
from unittest.mock import Mock, patch

import pytest
import requests
from django.test import TestCase, override_settings
from django_scopes import scopes_disabled

from pretix.plugins.socialauth.mediawiki_provider import (
    MediaWikiRateLimitException,
    RateLimitedOAuth2Client,
)


@pytest.fixture
@scopes_disabled()
def oauth_client():
    """Create a test OAuth2 client instance."""
    return RateLimitedOAuth2Client(
        client_id='test_client_id',
        client_secret='test_client_secret',
        access_token_url='https://meta.wikimedia.org/w/rest.php/oauth2/access_token',
    )


class TestMediaWikiRateLimitException(TestCase):
    """Test the custom rate limit exception following FOSSASIA patterns."""
    
    def test_exception_with_default_message(self):
        """Test that exception is created with default message."""
        exc = MediaWikiRateLimitException()
        
        self.assertIn("rate-limited", str(exc))
        self.assertEqual(exc.retry_after, 60)
    
    def test_exception_with_custom_message(self):
        """Test exception with custom message and parameters."""
        exc = MediaWikiRateLimitException(
            "Custom message with {time_desc}",
            {'time_desc': "2 minutes", 'retry_after': 120}
        )
        
        self.assertIn("Custom message with 2 minutes", str(exc))
        self.assertEqual(exc.retry_after, 120)


@scopes_disabled()
class TestRateLimitedOAuth2Client(TestCase):
    """Test MediaWiki OAuth client with proper rate limiting handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = RateLimitedOAuth2Client(
            client_id='test_client_id',
            client_secret='test_client_secret',
            access_token_url='https://meta.wikimedia.org/w/rest.php/oauth2/access_token',
        )
    
    def test_auto_generated_user_agent(self):
        """Test that auto-generated User-Agent follows Wikimedia conventions."""
        session = self.client._create_session()
        user_agent = session.headers.get('User-Agent')
        
        self.assertIsNotNone(user_agent)
        self.assertIn('EventyAY-Tickets', user_agent)
        self.assertIn('eventyay.com', user_agent)
        self.assertIn('requests/', user_agent)
        
        # Should follow format: ToolName/Version (URL; contact@email.com) LibraryName/Version
        self.assertRegex(user_agent, r'^EventyAY-Tickets/[\d\.]+ \(.+; .+@.+\) requests/[\d\.]+$')
    
    @override_settings(MEDIAWIKI_USER_AGENT='Custom-Agent/1.0 (https://example.com; test@example.com) requests/2.31.0')
    def test_custom_user_agent_setting(self):
        """Test that custom User-Agent setting is respected."""
        session = self.client._create_session()
        user_agent = session.headers.get('User-Agent')
        
        self.assertEqual(user_agent, 'Custom-Agent/1.0 (https://example.com; test@example.com) requests/2.31.0')
    
    @patch('requests.Session.request')
    def test_rate_limit_429_raises_exception_no_retry(self, mock_request):
        """Test that 429 responses raise MediaWikiRateLimitException without retrying."""
        # Mock a 429 response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        mock_request.return_value = mock_response
        
        # Should raise exception without retrying
        with self.assertRaises(MediaWikiRateLimitException) as cm:
            self.client._make_request('GET', 'https://test.com')
        
        # Check exception properties
        self.assertIn('rate-limited', str(cm.exception))
        self.assertEqual(cm.exception.retry_after, 60)
        
        # Should only make one request (no retries)
        self.assertEqual(mock_request.call_count, 1)
    
    @patch('requests.Session.request')
    def test_rate_limit_429_with_custom_retry_after(self, mock_request):
        """Test that custom Retry-After header is respected."""
        # Mock a 429 response with custom retry time
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '120'}
        mock_request.return_value = mock_response
        
        with self.assertRaises(MediaWikiRateLimitException) as cm:
            self.client._make_request('GET', 'https://test.com')
        
        self.assertEqual(cm.exception.retry_after, 120)
        self.assertIn('2 minute', str(cm.exception))
    
    @patch('requests.Session.request')
    def test_rate_limit_429_invalid_retry_after(self, mock_request):
        """Test handling of invalid Retry-After header."""
        # Mock a 429 response with invalid retry time
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': 'invalid'}
        mock_request.return_value = mock_response
        
        with self.assertRaises(MediaWikiRateLimitException) as cm:
            self.client._make_request('GET', 'https://test.com')
        
        # Should default to 60 seconds
        self.assertEqual(cm.exception.retry_after, 60)
    
    @patch('requests.Session.request')
    def test_successful_request(self, mock_request):
        """Test that successful requests work normally."""
        # Mock a successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_request.return_value = mock_response
        
        response = self.client._make_request('GET', 'https://test.com')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_request.call_count, 1)
    
    @patch('requests.Session.request')
    def test_other_http_errors_handled_normally(self, mock_request):
        """Test that non-429 HTTP errors are handled normally."""
        # Mock a 500 response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_request.return_value = mock_response
        
        with self.assertRaises(requests.exceptions.HTTPError):
            self.client._make_request('GET', 'https://test.com')
        
        # Should only make one request (no retries for non-429 errors)
        self.assertEqual(mock_request.call_count, 1)
    
    @patch('requests.Session.request')
    def test_get_access_token_rate_limited(self, mock_request):
        """Test get_access_token method with rate limiting."""
        # Mock a 429 response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        mock_request.return_value = mock_response
        
        with self.assertRaises(MediaWikiRateLimitException):
            self.client.get_access_token('test_code', 'https://redirect.uri')
    
    @patch('requests.Session.request')
    def test_get_access_token_successful(self, mock_request):
        """Test successful get_access_token call."""
        # Mock a successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_token',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        mock_request.return_value = mock_response
        
        result = self.client.get_access_token('test_code', 'https://redirect.uri')
        
        self.assertEqual(result['access_token'], 'test_token')
        self.assertEqual(mock_request.call_count, 1)
    
    @patch('requests.Session.request')
    def test_get_user_info_rate_limited(self, mock_request):
        """Test get_user_info method with rate limiting."""
        # Mock a 429 response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '90'}
        mock_request.return_value = mock_response
        
        with self.assertRaises(MediaWikiRateLimitException):
            self.client.get_user_info('test_access_token')
    
    @patch('requests.Session.request')
    def test_get_user_info_successful(self, mock_request):
        """Test successful get_user_info call."""
        # Mock a successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'query': {
                'userinfo': {
                    'name': 'TestUser',
                    'email': 'test@example.com'
                }
            }
        }
        mock_request.return_value = mock_response
        
        result = self.client.get_user_info('test_access_token')
        
        self.assertIn('query', result)
        self.assertEqual(mock_request.call_count, 1)
    
    def test_user_agent_generation_with_different_settings(self):
        """Test User-Agent generation with various settings configurations."""
        with override_settings(
            VERSION='2.1.0',
            SITE_URL='https://custom.eventyay.com',
            DEFAULT_FROM_EMAIL='admin@custom.eventyay.com'
        ):
            user_agent = self.client._get_user_agent()
            
            self.assertIn('EventyAY-Tickets/2.1.0', user_agent)
            self.assertIn('custom.eventyay.com', user_agent)
            self.assertIn('admin@custom.eventyay.com', user_agent)
    
    def test_user_agent_fallback_on_error(self):
        """Test User-Agent fallback when settings access fails."""
        # Test that fallback works even if settings are problematic
        with patch('pretix.plugins.socialauth.mediawiki_provider.settings') as mock_settings:
            mock_settings.MEDIAWIKI_USER_AGENT = None
            mock_settings.VERSION = None
            mock_settings.SITE_URL = None
            
            # Should not raise exception and should return a valid User-Agent
            user_agent = self.client._get_user_agent()
            
            self.assertIsInstance(user_agent, str)
            self.assertIn('EventyAY-Tickets', user_agent)


@scopes_disabled()
class TestMediaWikiProviderIntegration(TestCase):
    """Integration tests for the MediaWiki provider."""
    
    def test_provider_uses_custom_client(self):
        """Test that the provider uses our custom OAuth2 client."""
        from pretix.plugins.socialauth.mediawiki_provider import MediaWikiProvider
        
        provider = MediaWikiProvider(None)  # request=None for testing
        client_class = provider.get_oauth2_client_class()
        
        self.assertEqual(client_class, RateLimitedOAuth2Client)
