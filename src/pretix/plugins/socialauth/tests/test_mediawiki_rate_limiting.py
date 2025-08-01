"""
Tests for MediaWiki OAuth implementation with user-friendly rate limiting.

Tests focus on ensuring that users get vague, non-pressuring time descriptions
instead of exact retry times when encountering rate limits.
"""

from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django_scopes import scopes_disabled

from pretix.plugins.socialauth.mediawiki_provider import (
    MediaWikiRateLimitException,
    RateLimitedOAuth2Client,
)


@scopes_disabled()
class TestMediaWikiRateLimitException(TestCase):
    """Test MediaWiki rate limit exception with user-friendly messaging."""
    
    def test_default_exception_message(self):
        """Test exception with default user-friendly message."""
        exc = MediaWikiRateLimitException()
        
        self.assertIn("experiencing high traffic", str(exc))
        self.assertIn("try again in a few minutes", str(exc))
        self.assertIsNone(exc.retry_after)
    
    def test_custom_exception_with_vague_time(self):
        """Test exception with custom message and vague time description."""
        exc = MediaWikiRateLimitException(
            "Custom message with {time_desc}",
            {'time_desc': "a couple of minutes", 'retry_after': 120}
        )
        
        self.assertIn("Custom message with a couple of minutes", str(exc))
        self.assertEqual(exc.retry_after, 120)


@scopes_disabled()
class TestRateLimitedOAuth2Client(TestCase):
    """Test MediaWiki OAuth client with user-friendly rate limiting handling."""
    
    def setUp(self):
        """Set up test client."""
        self.client = RateLimitedOAuth2Client(
            request=None,
            client_id='test-client',
            client_secret='test-secret',
            access_token_method='POST',
            access_token_url='https://test.com/token',
            callback_url='https://test.com/callback',
            scope='test'
        )
    
    def test_get_friendly_time_description(self):
        """Test conversion of seconds to user-friendly descriptions."""
        # Test various time ranges
        self.assertEqual(self.client._get_friendly_time_description(30), "a minute")
        self.assertEqual(self.client._get_friendly_time_description(60), "a minute")
        self.assertEqual(self.client._get_friendly_time_description(90), "a couple of minutes")
        self.assertEqual(self.client._get_friendly_time_description(120), "a couple of minutes")
        self.assertEqual(self.client._get_friendly_time_description(180), "a few minutes")
        self.assertEqual(self.client._get_friendly_time_description(300), "a few minutes")
        self.assertEqual(self.client._get_friendly_time_description(450), "several minutes")
        self.assertEqual(self.client._get_friendly_time_description(600), "several minutes")
        self.assertEqual(self.client._get_friendly_time_description(900), "some time")
        
        # Test edge cases
        self.assertEqual(self.client._get_friendly_time_description(None), "a few minutes")
        self.assertEqual(self.client._get_friendly_time_description("invalid"), "a few minutes")
    
    @override_settings(MEDIAWIKI_USER_AGENT='Custom-Agent/1.0 (https://example.com; test@example.com) requests/2.31.0')
    def test_custom_user_agent(self):
        """Test that custom User-Agent is used when set."""
        user_agent = self.client._get_user_agent()
        self.assertEqual(user_agent, 'Custom-Agent/1.0 (https://example.com; test@example.com) requests/2.31.0')
    
    @patch('requests.Session.request')
    def test_rate_limit_with_user_friendly_message(self, mock_request):
        """Test that 429 responses show user-friendly messages without exact times."""
        # Mock a 429 response with 60 second retry
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        mock_request.return_value = mock_response
        
        # Should raise exception with vague time description
        with self.assertRaises(MediaWikiRateLimitException) as cm:
            self.client.request('GET', 'https://test.com')
        
        # Check that message is user-friendly and vague
        exception_str = str(cm.exception)
        self.assertIn('temporarily busy', exception_str)
        self.assertIn('a minute', exception_str)  # Vague, not "60 seconds"
        self.assertNotIn('60', exception_str)  # No exact time in user message
        
        # But retry_after should be tracked internally
        self.assertEqual(cm.exception.retry_after, 60)
        
        # Should only make one request (no retries)
        self.assertEqual(mock_request.call_count, 1)
    
    @patch('requests.Session.request')
    def test_rate_limit_with_longer_time(self, mock_request):
        """Test rate limiting with longer wait time gets appropriate vague description."""
        # Mock a 429 response with 5 minute retry
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '300'}
        mock_request.return_value = mock_response
        
        with self.assertRaises(MediaWikiRateLimitException) as cm:
            self.client.request('GET', 'https://test.com')
        
        exception_str = str(cm.exception)
        self.assertIn('a few minutes', exception_str)  # Vague description
        self.assertNotIn('300', exception_str)  # No exact seconds
        self.assertNotIn('5 minutes', exception_str)  # No exact minutes
        self.assertEqual(cm.exception.retry_after, 300)
    
    @patch('requests.Session.request')
    def test_rate_limit_invalid_retry_after(self, mock_request):
        """Test handling of invalid Retry-After header with default vague message."""
        # Mock a 429 response with invalid retry time
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': 'invalid'}
        mock_request.return_value = mock_response
        
        with self.assertRaises(MediaWikiRateLimitException) as cm:
            self.client.request('GET', 'https://test.com')
        
        # Should default to generic vague message
        exception_str = str(cm.exception)
        self.assertIn('a few minutes', exception_str)
        self.assertIsNone(cm.exception.retry_after)
    
    @patch('requests.Session.request')
    def test_rate_limit_no_retry_header(self, mock_request):
        """Test rate limiting without Retry-After header."""
        # Mock a 429 response without retry header
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        with self.assertRaises(MediaWikiRateLimitException) as cm:
            self.client.request('GET', 'https://test.com')
        
        # Should use default vague message
        exception_str = str(cm.exception)
        self.assertIn('a few minutes', exception_str)
        self.assertIsNone(cm.exception.retry_after)
    
    @patch('requests.Session.request')
    def test_successful_request(self, mock_request):
        """Test that successful requests work normally."""
        # Mock a successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_request.return_value = mock_response
        
        response = self.client.request('GET', 'https://test.com')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_request.call_count, 1)
    
    @patch('requests.Session.request')
    def test_other_http_errors_handled_normally(self, mock_request):
        """Test that non-429 HTTP errors are handled normally."""
        # Mock a 500 response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_request.return_value = mock_response
        
        response = self.client.request('GET', 'https://test.com')
        
        # Should not raise MediaWikiRateLimitException
        self.assertEqual(response.status_code, 500)
        self.assertEqual(mock_request.call_count, 1)
    
    def test_user_agent_generation(self):
        """Test automatic User-Agent generation."""
        with patch('pretix.plugins.socialauth.mediawiki_provider.settings') as mock_settings:
            mock_settings.MEDIAWIKI_USER_AGENT = None
            
            user_agent = self.client._get_user_agent()
            
            # Should contain expected components
            self.assertIn('eventyay-tickets/1.0', user_agent)
            self.assertIn('github.com/fossasia/eventyay-tickets', user_agent)
            self.assertIn('requests/', user_agent)
            self.assertIn('Python/', user_agent)


@scopes_disabled()
class TestMediaWikiProviderIntegration(TestCase):
    """Integration tests for the MediaWiki provider."""
    
    def test_provider_uses_custom_client(self):
        """Test that the MediaWiki provider uses our custom OAuth2 client."""
        try:
            from pretix.plugins.socialauth.mediawiki_provider import MediaWikiProvider
            
            provider = MediaWikiProvider(None)  # request=None for testing
            client_class = provider.get_oauth2_client_class()
            
            self.assertEqual(client_class, RateLimitedOAuth2Client)
        except ImportError:
            # Skip if base MediaWiki provider not available
            self.skipTest("Base MediaWiki provider not available")


class TestUserFriendlyTimeDescriptions(TestCase):
    """Test that all time descriptions are appropriately vague and user-friendly."""
    
    def test_no_exact_times_in_user_messages(self):
        """Ensure no exact times leak into user-facing messages."""
        client = RateLimitedOAuth2Client(
            request=None,
            client_id='test',
            client_secret='test',
            access_token_method='POST',
            access_token_url='https://test.com/token',
            callback_url='https://test.com/callback',
        )
        
        # Test various retry times - all should produce vague descriptions
        test_cases = [
            (30, "a minute"),
            (60, "a minute"),
            (90, "a couple of minutes"),
            (120, "a couple of minutes"),
            (180, "a few minutes"),
            (300, "a few minutes"),
            (450, "several minutes"),
            (600, "several minutes"),
            (900, "some time"),
        ]
        
        for seconds, expected_desc in test_cases:
            with self.subTest(seconds=seconds):
                desc = client._get_friendly_time_description(seconds)
                self.assertEqual(desc, expected_desc)
                
                # Ensure no exact numbers in description
                self.assertNotIn(str(seconds), desc)
                self.assertNotIn(f"{seconds//60}", desc)  # No exact minutes either
    
    def test_user_friendly_language(self):
        """Test that all descriptions use friendly, non-technical language."""
        client = RateLimitedOAuth2Client(
            request=None,
            client_id='test',
            client_secret='test',
            access_token_method='POST',
            access_token_url='https://test.com/token',
            callback_url='https://test.com/callback',
        )
        
        # All descriptions should be friendly
        friendly_terms = [
            "a minute", "a couple of minutes", "a few minutes", 
            "several minutes", "some time"
        ]
        
        for seconds in [30, 60, 90, 120, 180, 300, 450, 600, 900, 1200]:
            desc = client._get_friendly_time_description(seconds)
            self.assertIn(desc, friendly_terms)
            
            # Should not contain technical terms
            self.assertNotIn('retry', desc.lower())
            self.assertNotIn('timeout', desc.lower())
            self.assertNotIn('limit', desc.lower())
            self.assertNotIn('seconds', desc.lower())
