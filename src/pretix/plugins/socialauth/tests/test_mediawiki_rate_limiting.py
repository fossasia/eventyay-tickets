"""
Tests for MediaWiki OAuth rate limiting implementation.
"""
import time
from unittest.mock import Mock, patch, MagicMock
import pytest
import requests
from django.test import TestCase, override_settings
from django.core.cache import cache

from pretix.plugins.socialauth.mediawiki_provider import RateLimitedOAuth2Client


class TestRateLimitedOAuth2Client(TestCase):
    """Test rate limiting functionality for MediaWiki OAuth client."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = RateLimitedOAuth2Client(
            client_id='test_client_id',
            client_secret='test_client_secret',
            access_token_url='https://meta.wikimedia.org/w/rest.php/oauth2/access_token',
        )
        # Clear cache before each test
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
    
    def test_user_agent_header_set(self):
        """Test that proper User-Agent header is set."""
        session = self.client._create_session()
        user_agent = session.headers.get('User-Agent')
        
        self.assertIsNotNone(user_agent)
        self.assertIn('EventyAY-Tickets', user_agent)
        self.assertIn('eventyay.com', user_agent)
        self.assertIn('django-allauth', user_agent)
    
    @override_settings(MEDIAWIKI_USER_AGENT='Custom-Agent/1.0 (test@example.com)')
    def test_custom_user_agent_setting(self):
        """Test that custom User-Agent setting is respected."""
        session = self.client._create_session()
        user_agent = session.headers.get('User-Agent')
        
        self.assertEqual(user_agent, 'Custom-Agent/1.0 (test@example.com)')
    
    def test_rate_limit_check_initial(self):
        """Test initial rate limit check allows requests."""
        self.assertTrue(self.client._check_rate_limit())
    
    def test_rate_limit_check_exceeds_limit(self):
        """Test rate limit check blocks when limit exceeded."""
        # Fill up the rate limit
        for _ in range(self.client.MAX_REQUESTS_PER_WINDOW):
            self.assertTrue(self.client._check_rate_limit())
        
        # Next request should be blocked
        self.assertFalse(self.client._check_rate_limit())
    
    def test_rate_limit_window_sliding(self):
        """Test that rate limit window slides correctly."""
        # Mock time to control window sliding
        with patch('time.time') as mock_time:
            start_time = 1000.0
            mock_time.return_value = start_time
            
            # Fill up the rate limit
            for _ in range(self.client.MAX_REQUESTS_PER_WINDOW):
                self.assertTrue(self.client._check_rate_limit())
            
            # Should be blocked
            self.assertFalse(self.client._check_rate_limit())
            
            # Move time forward beyond window
            mock_time.return_value = start_time + self.client.RATE_LIMIT_WINDOW + 1
            
            # Should be allowed again
            self.assertTrue(self.client._check_rate_limit())
    
    def test_backoff_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        self.assertEqual(self.client._get_backoff_delay(0), 1.0)
        self.assertEqual(self.client._get_backoff_delay(1), 2.0)
        self.assertEqual(self.client._get_backoff_delay(2), 4.0)
        self.assertEqual(self.client._get_backoff_delay(10), self.client.MAX_BACKOFF_DELAY)
    
    @patch('time.sleep')
    def test_wait_for_rate_limit(self, mock_sleep):
        """Test waiting for rate limit with backoff."""
        self.client._wait_for_rate_limit(0)
        mock_sleep.assert_called_once_with(1.0)
        
        mock_sleep.reset_mock()
        self.client._wait_for_rate_limit(2)
        mock_sleep.assert_called_once_with(4.0)
    
    @patch('time.sleep')
    def test_make_request_success(self, mock_sleep):
        """Test successful request without rate limiting."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {'access_token': 'test_token'}
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            response = self.client._make_request_with_retries('POST', 'https://example.com')
            
        self.assertEqual(response.status_code, 200)
        mock_sleep.assert_not_called()
    
    @patch('time.sleep')
    def test_make_request_rate_limited_429(self, mock_sleep):
        """Test handling of HTTP 429 responses."""
        # First response is rate limited, second succeeds
        rate_limited_response = Mock(spec=requests.Response)
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {}
        
        success_response = Mock(spec=requests.Response)
        success_response.status_code = 200
        success_response.json.return_value = {'access_token': 'test_token'}
        
        with patch.object(self.client.session, 'request', side_effect=[rate_limited_response, success_response]):
            with patch.object(self.client, '_check_rate_limit', return_value=True):
                response = self.client._make_request_with_retries('POST', 'https://example.com')
        
        self.assertEqual(response.status_code, 200)
        mock_sleep.assert_called()
    
    @patch('time.sleep')
    def test_make_request_retry_after_header(self, mock_sleep):
        """Test handling of Retry-After header."""
        rate_limited_response = Mock(spec=requests.Response)
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {'Retry-After': '5'}
        
        success_response = Mock(spec=requests.Response)
        success_response.status_code = 200
        
        with patch.object(self.client.session, 'request', side_effect=[rate_limited_response, success_response]):
            with patch.object(self.client, '_check_rate_limit', return_value=True):
                response = self.client._make_request_with_retries('POST', 'https://example.com')
        
        self.assertEqual(response.status_code, 200)
        # Should sleep for the Retry-After duration
        mock_sleep.assert_any_call(5.0)
    
    @patch('time.sleep')
    def test_make_request_max_retries_exceeded(self, mock_sleep):
        """Test that exception is raised after max retries."""
        rate_limited_response = Mock(spec=requests.Response)
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {}
        
        with patch.object(self.client.session, 'request', return_value=rate_limited_response):
            with patch.object(self.client, '_check_rate_limit', return_value=True):
                with self.assertRaises(Exception) as context:
                    self.client._make_request_with_retries('POST', 'https://example.com', max_retries=2)
                
                self.assertIn('rate limited (HTTP 429)', str(context.exception))
    
    @patch('time.sleep')
    def test_make_request_client_rate_limit_exceeded(self, mock_sleep):
        """Test handling when client-side rate limit is exceeded."""
        with patch.object(self.client, '_check_rate_limit', return_value=False):
            with self.assertRaises(Exception) as context:
                self.client._make_request_with_retries('POST', 'https://example.com', max_retries=2)
            
            self.assertIn('rate limit exceeded after maximum retries', str(context.exception))
    
    @patch('time.sleep')
    def test_make_request_server_error_retry(self, mock_sleep):
        """Test retry on server errors."""
        server_error_response = Mock(spec=requests.Response)
        server_error_response.status_code = 500
        
        success_response = Mock(spec=requests.Response)
        success_response.status_code = 200
        
        with patch.object(self.client.session, 'request', side_effect=[server_error_response, success_response]):
            with patch.object(self.client, '_check_rate_limit', return_value=True):
                response = self.client._make_request_with_retries('POST', 'https://example.com')
        
        self.assertEqual(response.status_code, 200)
        mock_sleep.assert_called()
    
    def test_get_access_token_integration(self):
        """Test get_access_token method integration."""
        mock_response = Mock(spec=requests.Response)
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        
        with patch.object(self.client, '_make_request_with_retries', return_value=mock_response):
            result = self.client.get_access_token('test_code', 'https://example.com/callback')
        
        expected_result = {
            'access_token': 'test_access_token',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        self.assertEqual(result, expected_result)
    
    def test_get_user_info_integration(self):
        """Test get_user_info method integration."""
        mock_response = Mock(spec=requests.Response)
        mock_response.json.return_value = {
            'query': {
                'userinfo': {
                    'id': 12345,
                    'name': 'TestUser',
                    'email': 'test@example.com',
                    'realname': 'Test User'
                }
            }
        }
        
        with patch.object(self.client, '_make_request_with_retries', return_value=mock_response):
            result = self.client.get_user_info('test_access_token')
        
        self.assertIn('query', result)
        self.assertIn('userinfo', result['query'])


@pytest.mark.django_db
class TestMediaWikiProviderIntegration(TestCase):
    """Integration tests for the custom MediaWiki provider."""
    
    def test_provider_uses_rate_limited_client(self):
        """Test that the provider uses our custom rate-limited client."""
        from pretix.plugins.socialauth.mediawiki_provider import MediaWikiProvider
        
        provider = MediaWikiProvider(request=None)
        client_class = provider.get_oauth2_client_class()
        
        self.assertEqual(client_class, RateLimitedOAuth2Client)
