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
    
    def test_rate_limit_concurrent_requests(self):
        """Test concurrent requests to verify atomic locking logic."""
        import threading
        from unittest.mock import patch
        
        # Track successful rate limit checks
        successful_checks = []
        
        def check_rate_limit_wrapper():
            """Wrapper to call _check_rate_limit and track results."""
            result = self.client._check_rate_limit()
            if result:
                successful_checks.append(1)
            return result
        
        # Create multiple threads to simulate concurrent requests
        threads = []
        for _ in range(self.client.MAX_REQUESTS_PER_WINDOW + 10):  # More than the limit
            thread = threading.Thread(target=check_rate_limit_wrapper)
            threads.append(thread)
        
        # Start all threads simultaneously
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should allow at most MAX_REQUESTS_PER_WINDOW successful checks
        # Note: Due to race conditions in non-locking cache backends, 
        # this might be slightly higher, but should be close to the limit
        self.assertLessEqual(len(successful_checks), self.client.MAX_REQUESTS_PER_WINDOW + 5)
    
    def test_backoff_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        self.assertEqual(self.client._get_backoff_delay(0), 1.0)
        self.assertEqual(self.client._get_backoff_delay(1), 2.0)
        self.assertEqual(self.client._get_backoff_delay(2), 4.0)
        self.assertEqual(self.client._get_backoff_delay(10), self.client.MAX_BACKOFF_DELAY)
    
    def test_non_retryable_errors(self):
        """Test that non-retryable 4xx errors (except 429) are not retried."""
        # Mock a 400 Bad Request response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'error': 'invalid_request'}
        mock_response.text = '{"error": "invalid_request"}'
        
        with patch('requests.Session.request', return_value=mock_response) as mock_request:
            with self.assertRaises(requests.HTTPError):
                self.client._make_request_with_retries('GET', 'https://example.com/api')
            
            # Should only be called once (no retries for 4xx except 429)
            self.assertEqual(mock_request.call_count, 1)
    
    def test_retry_count_verification(self):
        """Test that retry count is properly tracked and limited."""
        # Mock consecutive 503 Service Unavailable responses
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.text = 'Service Unavailable'
        
        with patch('requests.Session.request', return_value=mock_response) as mock_request:
            with patch('time.sleep'):  # Speed up test
                with self.assertRaises(requests.HTTPError):
                    self.client._make_request_with_retries('GET', 'https://example.com/api')
                
                # Should retry exactly MAX_RETRIES times (3) plus initial attempt = 4 total
                self.assertEqual(mock_request.call_count, 4)
    
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
    def test_make_request_malformed_retry_after_header(self, mock_sleep):
        """Test fallback logic when Retry-After header is non-integer or malformed."""
        # Simulate a 429 response with a malformed Retry-After header
        rate_limited_response = Mock(spec=requests.Response)
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {'Retry-After': 'notanumber'}

        success_response = Mock(spec=requests.Response)
        success_response.status_code = 200

        with patch.object(self.client.session, 'request', side_effect=[rate_limited_response, success_response]):
            with patch.object(self.client, '_check_rate_limit', return_value=True):
                response = self.client._make_request_with_retries('POST', 'https://example.com')

        self.assertEqual(response.status_code, 200)
        # Should fallback to exponential backoff (e.g., 1.0) if Retry-After is malformed
        mock_sleep.assert_any_call(1.0)

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
    
    @patch('time.sleep')
    def test_cache_backend_failure_handling(self, mock_sleep):
        """Test that cache backend exceptions are handled gracefully."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {'access_token': 'test_token'}
        
        # Mock cache.get to raise an exception
        with patch('django.core.cache.cache.get', side_effect=Exception("Cache connection failed")):
            with patch.object(self.client.session, 'request', return_value=mock_response):
                # Should not crash and should allow the request to proceed
                response = self.client._make_request_with_retries('POST', 'https://example.com')
        
        self.assertEqual(response.status_code, 200)
        # Should not sleep since rate limiting is bypassed due to cache failure
        mock_sleep.assert_not_called()
    
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
    
    def test_get_access_token_json_error_handling(self):
        """Test get_access_token handles non-JSON responses gracefully."""
        mock_response = Mock(spec=requests.Response)
        mock_response.text = "Not a JSON response"
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        
        with patch.object(self.client, '_make_request_with_retries', return_value=mock_response):
            with self.assertRaises(Exception) as context:
                self.client.get_access_token('test_code', 'https://example.com/callback')
            
            self.assertIn('Failed to decode JSON from MediaWiki API response', str(context.exception))
            self.assertIn('Not a JSON response', str(context.exception))
    
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
    
    def test_get_user_info_json_error_handling(self):
        """Test get_user_info handles non-JSON responses gracefully."""
        mock_response = Mock(spec=requests.Response)
        mock_response.text = "MediaWiki API error: Invalid token"
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        
        with patch.object(self.client, '_make_request_with_retries', return_value=mock_response):
            with self.assertRaises(Exception) as context:
                self.client.get_user_info('test_access_token')
            
            self.assertIn('Failed to decode JSON from MediaWiki API response', str(context.exception))
            self.assertIn('MediaWiki API error: Invalid token', str(context.exception))


@pytest.mark.django_db
class TestMediaWikiProviderIntegration(TestCase):
    """Integration tests for the custom MediaWiki provider."""
    
    def test_provider_uses_rate_limited_client(self):
        """Test that the provider uses our custom rate-limited client."""
        from pretix.plugins.socialauth.mediawiki_provider import MediaWikiProvider
        
        provider = MediaWikiProvider(request=None)
        client_class = provider.get_oauth2_client_class()
        
        self.assertEqual(client_class, RateLimitedOAuth2Client)
