"""
Tests for MediaWiki OAuth provider with user-friendly rate limiting.

This test suite ensures that rate limiting provides user-friendly messages
without exposing specific retry times, as requested in issue #817.
"""

import time
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth.models import User
from django_scopes import scopes_disabled

from pretix.plugins.socialauth.mediawiki_provider import (
    MediaWikiRateLimitException,
    RateLimitedOAuth2Client,
    MediaWikiProvider
)


class MediaWikiRateLimitingTest(TestCase):
    """Test suite for MediaWiki rate limiting functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.provider = MediaWikiProvider(None)
    
    def test_rate_limit_exception_with_30_seconds(self):
        """Test that 30 seconds becomes 'a minute' - user-friendly."""
        exception = MediaWikiRateLimitException(retry_after_seconds=30)
        message = str(exception)
        
        # Should contain friendly time description, not exact seconds
        self.assertIn("a minute", message)
        self.assertNotIn("30", message)
        self.assertNotIn("second", message)
    
    def test_rate_limit_exception_with_120_seconds(self):
        """Test that 120 seconds becomes 'a couple of minutes'."""
        exception = MediaWikiRateLimitException(retry_after_seconds=120)
        message = str(exception)
        
        self.assertIn("a couple of minutes", message)
        self.assertNotIn("120", message)
        self.assertNotIn("second", message)
    
    def test_rate_limit_exception_with_300_seconds(self):
        """Test that 300 seconds becomes 'a few minutes'."""
        exception = MediaWikiRateLimitException(retry_after_seconds=300)
        message = str(exception)
        
        self.assertIn("a few minutes", message)
        self.assertNotIn("300", message)
        self.assertNotIn("second", message)
    
    def test_rate_limit_exception_with_large_value(self):
        """Test that large values become 'a little while'."""
        exception = MediaWikiRateLimitException(retry_after_seconds=1200)
        message = str(exception)
        
        self.assertIn("a little while", message)
        self.assertNotIn("1200", message)
        self.assertNotIn("second", message)
    
    def test_rate_limit_exception_with_no_time(self):
        """Test fallback when no retry time is provided."""
        exception = MediaWikiRateLimitException()
        message = str(exception)
        
        self.assertIn("a moment", message)
        self.assertIn("MediaWiki is currently experiencing high traffic", message)
    
    def test_rate_limit_exception_with_custom_message(self):
        """Test that custom messages are preserved."""
        custom_message = "Custom rate limit message"
        exception = MediaWikiRateLimitException(
            retry_after_seconds=60, 
            message=custom_message
        )
        
        self.assertEqual(str(exception), custom_message)
    
    def test_friendly_time_conversion_edge_cases(self):
        """Test edge cases in time conversion."""
        exception = MediaWikiRateLimitException()
        
        # Test various time ranges
        test_cases = [
            (0, "a moment"),
            (15, "a minute"),
            (30, "a minute"),
            (90, "a couple of minutes"),
            (120, "a couple of minutes"),
            (200, "a few minutes"),
            (300, "a few minutes"),
            (450, "several minutes"),
            (600, "several minutes"),
            (900, "a little while"),
        ]
        
        for seconds, expected in test_cases:
            result = exception._get_friendly_time_description(seconds)
            self.assertEqual(result, expected, 
                           f"Failed for {seconds} seconds: got {result}, expected {expected}")
    
    @patch('pretix.plugins.socialauth.mediawiki_provider.logger')
    def test_rate_limited_client_handles_429_response(self, mock_logger):
        """Test that 429 responses are converted to user-friendly exceptions."""
        # Mock the underlying OAuth2 client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        
        # Create OAuth2Error with 429 response
        from allauth.socialaccount.providers.oauth2.client import OAuth2Error
        oauth_error = OAuth2Error("Rate limited")
        oauth_error.response = mock_response
        
        mock_client.get_access_token.side_effect = oauth_error
        
        # Test our rate-limited client
        rate_limited_client = RateLimitedOAuth2Client(mock_client)
        
        with self.assertRaises(MediaWikiRateLimitException) as cm:
            rate_limited_client.get_access_token("test_code")
        
        # Verify the exception has user-friendly message
        exception = cm.exception
        self.assertEqual(exception.retry_after_seconds, 60)
        
        # Verify logging occurred
        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]
        self.assertIn("MediaWiki OAuth rate limit hit", log_message)
        self.assertIn("user-friendly error", log_message)
    
    def test_rate_limited_client_handles_missing_retry_after(self):
        """Test handling of 429 responses without Retry-After header."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {}  # No Retry-After header
        
        from allauth.socialaccount.providers.oauth2.client import OAuth2Error
        oauth_error = OAuth2Error("Rate limited")
        oauth_error.response = mock_response
        
        mock_client.get_access_token.side_effect = oauth_error
        
        rate_limited_client = RateLimitedOAuth2Client(mock_client)
        
        with self.assertRaises(MediaWikiRateLimitException) as cm:
            rate_limited_client.get_access_token("test_code")
        
        # Should still work with None retry time
        exception = cm.exception
        self.assertIsNone(exception.retry_after_seconds)
        self.assertIn("a moment", str(exception))
    
    def test_rate_limited_client_passes_through_other_errors(self):
        """Test that non-429 errors are passed through unchanged."""
        mock_client = Mock()
        
        from allauth.socialaccount.providers.oauth2.client import OAuth2Error
        oauth_error = OAuth2Error("Different error")
        mock_client.get_access_token.side_effect = oauth_error
        
        rate_limited_client = RateLimitedOAuth2Client(mock_client)
        
        # Should re-raise the original error, not convert it
        with self.assertRaises(OAuth2Error) as cm:
            rate_limited_client.get_access_token("test_code")
        
        self.assertEqual(cm.exception, oauth_error)
    
    def test_provider_basic_functionality(self):
        """Test basic provider functionality works correctly."""
        provider = MediaWikiProvider(None)
        
        # Test basic properties
        self.assertEqual(provider.id, 'mediawiki')
        self.assertEqual(provider.name, 'MediaWiki')
        self.assertEqual(provider.get_default_scope(), ['identify'])
        
        # Test data extraction
        test_data = {
            'sub': '12345',
            'username': 'testuser',
            'email': 'test@example.com',
            'given_name': 'Test',
            'family_name': 'User'
        }
        
        uid = provider.extract_uid(test_data)
        self.assertEqual(uid, '12345')
        
        fields = provider.extract_common_fields(test_data)
        expected_fields = {
            'username': 'testuser',
            'email': 'test@example.com', 
            'first_name': 'Test',
            'last_name': 'User'
        }
        self.assertEqual(fields, expected_fields)
    
    def test_no_exact_times_leak_to_users(self):
        """Critical test: ensure no exact retry times leak to users."""
        test_retry_times = [30, 60, 120, 300, 600, 900, 1200]
        
        for retry_time in test_retry_times:
            exception = MediaWikiRateLimitException(retry_after_seconds=retry_time)
            message = str(exception)
            
            # Critical: message should never contain exact seconds
            self.assertNotIn(str(retry_time), message, 
                           f"Exact time {retry_time} leaked in message: {message}")
            self.assertNotIn("second", message.lower(),
                           f"Word 'second' found in message: {message}")
            
            # Should contain helpful but vague guidance
            vague_terms = ["moment", "minute", "minutes", "while", "couple", "few", "several"]
            contains_vague_term = any(term in message.lower() for term in vague_terms)
            self.assertTrue(contains_vague_term, 
                          f"Message should contain vague time term: {message}")


@scopes_disabled()
class MediaWikiIntegrationTest(TestCase):
    """Integration tests for MediaWiki OAuth provider."""
    
    def test_provider_registration(self):
        """Test that the provider can be properly registered."""
        from pretix.plugins.socialauth.mediawiki_provider import provider_classes
        
        self.assertEqual(len(provider_classes), 1)
        self.assertEqual(provider_classes[0].__name__, 'MediaWikiProvider')
    
    def test_account_representation(self):
        """Test MediaWiki account representation."""
        from pretix.plugins.socialauth.mediawiki_provider import MediaWikiAccount
        
        # Mock account with extra data
        mock_account = Mock()
        mock_account.extra_data = {
            'username': 'testuser',
            'profile_url': 'https://en.wikipedia.org/wiki/User:testuser'
        }
        
        account = MediaWikiAccount(mock_account)
        
        self.assertEqual(account.get_profile_url(), 'https://en.wikipedia.org/wiki/User:testuser')
        self.assertIsNone(account.get_avatar_url())  # MediaWiki doesn't provide avatars
        self.assertEqual(account.to_str(), 'testuser')
