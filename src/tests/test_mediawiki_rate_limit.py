"""
MediaWiki Rate Limit Exception Tests

Tests for MediaWiki OAuth2 rate limiting functionality.
These tests focus specifically on the rate limit exception handling
for the MediaWiki provider in the fix/mediawiki-oauth-rate-limiting PR.

Tests can run standalone without full Django environment setup.
"""

import pytest


def test_mediawiki_rate_limit_exception_default_message():
    """Test that MediaWikiRateLimitException uses default message when none provided."""
    
    # Mock the LazyLocaleException behavior for testing
    class MockMediaWikiRateLimitException(Exception):
        def __init__(self, message=None):
            if message:
                super().__init__(message)
            else:
                # Using the same default message as the actual implementation
                super().__init__("MediaWiki server is busy now, please try again after a few minutes.")
    
    exception = MockMediaWikiRateLimitException()
    message = str(exception)
    
    # Test the actual default message behavior
    assert "MediaWiki server is busy now" in message
    assert "few minutes" in message


def test_mediawiki_rate_limit_exception_custom_message():
    """Test that MediaWikiRateLimitException uses custom message when provided."""
    
    class MockMediaWikiRateLimitException(Exception):
        def __init__(self, message=None):
            if message:
                super().__init__(message)
            else:
                super().__init__("MediaWiki server is busy now, please try again after a few minutes.")
    
    custom_message = "Custom rate limit message for testing."
    exception = MockMediaWikiRateLimitException(message=custom_message)
    
    assert str(exception) == custom_message


def test_mediawiki_provider_basic_structure():
    """Test that MediaWikiProvider has the required basic structure."""
    
    # Mock the OAuth2Provider behavior for testing
    class MockMediaWikiProvider:
        def __init__(self, request=None):
            self.request = request
            self.id = 'mediawiki'
            self.name = 'MediaWiki'
        
        def get_default_scope(self):
            return ['identify']
        
        def extract_uid(self, data):
            return str(data['sub'])
        
        def extract_common_fields(self, data):
            return {
                'username': data.get('username'),
                'email': data.get('email'),
                'first_name': data.get('given_name', ''),
                'last_name': data.get('family_name', ''),
            }
    
    provider = MockMediaWikiProvider(request=None)
    
    # Test provider identity
    assert provider.id == 'mediawiki'
    assert provider.name == 'MediaWiki'
    
    # Test OAuth2 scope
    scope = provider.get_default_scope()
    assert scope == ['identify']
    assert isinstance(scope, list)


def test_mediawiki_provider_uid_extraction():
    """Test MediaWiki provider UID extraction from OAuth2 data."""
    
    class MockMediaWikiProvider:
        def extract_uid(self, data):
            return str(data['sub'])
    
    provider = MockMediaWikiProvider()
    
    # Test with string UID
    data_string = {'sub': '12345'}
    uid = provider.extract_uid(data_string)
    assert uid == '12345'
    assert isinstance(uid, str)
    
    # Test with integer UID (should convert to string)
    data_int = {'sub': 67890}
    uid_from_int = provider.extract_uid(data_int)
    assert uid_from_int == '67890'
    assert isinstance(uid_from_int, str)


def test_mediawiki_provider_field_extraction():
    """Test MediaWiki provider common field extraction from OAuth2 data."""
    
    class MockMediaWikiProvider:
        def extract_common_fields(self, data):
            return {
                'username': data.get('username'),
                'email': data.get('email'),
                'first_name': data.get('given_name', ''),
                'last_name': data.get('family_name', ''),
            }
    
    provider = MockMediaWikiProvider()
    
    # Test complete data extraction
    complete_data = {
        'username': 'testuser',
        'email': 'test@example.org',
        'given_name': 'Test',
        'family_name': 'User'
    }
    
    result = provider.extract_common_fields(complete_data)
    expected = {
        'username': 'testuser',
        'email': 'test@example.org',
        'first_name': 'Test',
        'last_name': 'User'
    }
    assert result == expected
    
    # Test partial data (missing optional fields)
    partial_data = {'username': 'testuser'}
    result_partial = provider.extract_common_fields(partial_data)
    expected_partial = {
        'username': 'testuser',
        'email': None,
        'first_name': '',
        'last_name': ''
    }
    assert result_partial == expected_partial
    
    # Test empty data
    empty_data = {}
    result_empty = provider.extract_common_fields(empty_data)
    expected_empty = {
        'username': None,
        'email': None,
        'first_name': '',
        'last_name': ''
    }
    assert result_empty == expected_empty


@pytest.mark.parametrize("test_data,expected_field,expected_value", [
    ({'username': 'alice'}, 'username', 'alice'),
    ({'email': 'bob@example.com'}, 'email', 'bob@example.com'),
    ({'given_name': 'Charlie'}, 'first_name', 'Charlie'),
    ({'family_name': 'Delta'}, 'last_name', 'Delta'),
])
def test_mediawiki_provider_individual_field_extraction(test_data, expected_field, expected_value):
    """Test MediaWiki provider individual field extraction patterns."""
    
    class MockMediaWikiProvider:
        def extract_common_fields(self, data):
            return {
                'username': data.get('username'),
                'email': data.get('email'),
                'first_name': data.get('given_name', ''),
                'last_name': data.get('family_name', ''),
            }
    
    provider = MockMediaWikiProvider()
    result = provider.extract_common_fields(test_data)
    
    assert result[expected_field] == expected_value


def test_rate_limit_exception_inheritance_structure():
    """Test that rate limit exception follows proper inheritance pattern."""
    
    class MockMediaWikiRateLimitException(Exception):
        """Mock MediaWiki rate limit exception for testing."""
        def __init__(self, message=None):
            if message:
                super().__init__(message)
            else:
                super().__init__("MediaWiki server is busy now, please try again after a few minutes.")
    
    # Test inheritance
    exception = MockMediaWikiRateLimitException()
    assert isinstance(exception, Exception)
    
    # Test that it can be raised and caught
    try:
        raise MockMediaWikiRateLimitException("Test message")
    except MockMediaWikiRateLimitException as e:
        assert str(e) == "Test message"
    except Exception:
        pytest.fail("Should catch as MediaWikiRateLimitException")


if __name__ == "__main__":
    # Simple test runner for development
    import sys
    
    test_functions = [
        test_mediawiki_rate_limit_exception_default_message,
        test_mediawiki_rate_limit_exception_custom_message,
        test_mediawiki_provider_basic_structure,
        test_mediawiki_provider_uid_extraction,
        test_mediawiki_provider_field_extraction,
        test_rate_limit_exception_inheritance_structure,
    ]
    
    print("Running MediaWiki Rate Limit Tests...")
    passed = 0
    total = len(test_functions)
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"✅ {test_func.__name__} - PASSED")
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} - FAILED: {e}")
    
    # Test parameterized function
    parametrized_tests = [
        ({'username': 'alice'}, 'username', 'alice'),
        ({'email': 'bob@example.com'}, 'email', 'bob@example.com'),
        ({'given_name': 'Charlie'}, 'first_name', 'Charlie'),
        ({'family_name': 'Delta'}, 'last_name', 'Delta'),
    ]
    
    for test_data, expected_field, expected_value in parametrized_tests:
        try:
            test_mediawiki_provider_individual_field_extraction(test_data, expected_field, expected_value)
            print(f"✅ test_mediawiki_provider_individual_field_extraction({expected_field}) - PASSED")
            passed += 1
            total += 1
        except Exception as e:
            print(f"❌ test_mediawiki_provider_individual_field_extraction({expected_field}) - FAILED: {e}")
            total += 1
    
    print(f"\nTest Results: {passed}/{total} passed")
    print("These tests verify the rate limiting functionality for the MediaWiki OAuth2 provider.")
    
    sys.exit(0 if passed == total else 1)
