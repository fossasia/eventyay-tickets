# MediaWiki OAuth Rate Limiting Implementation - Summary

## Overview
This implementation addresses issue #817 by implementing proper MediaWiki OAuth rate limiting that complies with Wikimedia API usage guidelines. The key changes remove retry logic for 429 errors and implement proper User-Agent strings as requested by the maintainer.

## Key Requirements Addressed

### 1. Remove Retry Logic for 429 Errors
- **Problem**: Previous implementation would retry requests when receiving 429 (Too Many Requests) responses, putting additional pressure on Wikimedia servers
- **Solution**: New implementation raises `MediaWikiRateLimitException` immediately without retrying
- **Benefit**: Respects Wikimedia servers and provides clear feedback to users

### 2. Proper User-Agent Implementation
- **Problem**: Using generic User-Agent from requests library doesn't identify the application properly
- **Solution**: Auto-generated User-Agent following Wikimedia conventions: `ToolName/Version (URL; contact@email.com) LibraryName/Version`
- **Benefit**: Complies with Wikimedia User-Agent policy and helps with request identification

## Implementation Details

### Files Modified

#### 1. `mediawiki_provider.py`
- **New Classes**:
  - `MediaWikiRateLimitException`: Custom exception for user-friendly rate limit errors
  - `RateLimitedOAuth2Client`: Custom OAuth2 client with proper rate limiting
  - `MediaWikiProvider`: Custom provider using the rate-limited client

- **Key Methods**:
  - `_get_user_agent()`: Auto-generates compliant User-Agent string
  - `_handle_rate_limit_response()`: Handles 429 responses without retrying
  - `_make_request()`: Makes HTTP requests with proper error handling

#### 2. `settings.py`
- Commented out hardcoded `MEDIAWIKI_USER_AGENT` to use auto-generation
- Settings can still override with custom User-Agent if needed

#### 3. `test_mediawiki_rate_limiting.py`
- Comprehensive test suite covering:
  - User-Agent generation (auto and custom)
  - Rate limit exception handling
  - No-retry behavior verification
  - Integration with django-allauth

## Technical Features

### User-Agent Generation
```python
# Auto-generated format:
"EventyAY-Tickets/2.0.0 (https://eventyay.com; info@eventyay.com) requests/2.31.0"

# Uses settings:
- VERSION: Application version
- SITE_URL: Application URL
- DEFAULT_FROM_EMAIL: Contact email
- requests.__version__: Library version
```

### Rate Limit Handling
```python
# On 429 response:
1. Parse Retry-After header (default: 60 seconds)
2. Log warning for monitoring
3. Raise MediaWikiRateLimitException with user-friendly message
4. NO RETRY - respects server load
```

### Exception Design
```python
class MediaWikiRateLimitException(Exception):
    def __init__(self, message="...", retry_after=60):
        self.retry_after = retry_after  # For programmatic access
        # Human-friendly message for UI display
```

## Benefits

### 1. Wikimedia Compliance
- ✅ Proper User-Agent identification
- ✅ No automatic retries on rate limits
- ✅ Respectful server usage

### 2. User Experience
- ✅ Clear error messages in natural language
- ✅ Specific retry time information
- ✅ No hanging requests

### 3. Maintainability
- ✅ Configurable via Django settings
- ✅ Comprehensive test coverage
- ✅ Proper logging for monitoring

## Configuration Options

### Auto User-Agent (Default)
```python
# settings.py - No configuration needed
# Uses VERSION, SITE_URL, DEFAULT_FROM_EMAIL automatically
```

### Custom User-Agent
```python
# settings.py
MEDIAWIKI_USER_AGENT = "CustomApp/1.0 (https://example.com; admin@example.com) requests/2.31.0"
```

## Testing

The test suite covers:
- ✅ Auto-generated User-Agent format validation
- ✅ Custom User-Agent setting respect
- ✅ 429 response handling without retries
- ✅ Retry-After header parsing
- ✅ Invalid header handling with defaults
- ✅ Successful request processing
- ✅ Non-429 error passthrough
- ✅ OAuth flow integration

## Migration Path

1. **Backward Compatible**: Existing configurations continue to work
2. **Auto-Upgrade**: User-Agent automatically improves without changes
3. **Gradual Rollout**: Can test with custom User-Agent first

## Monitoring & Debugging

### Logs to Watch For
```
# Rate limiting events
WARNING: MediaWiki OAuth rate limited (HTTP 429). User should try again in 60 seconds.

# User-Agent generation
DEBUG: Generated MediaWiki User-Agent: EventyAY-Tickets/2.0.0 (...)

# Fallback scenarios
WARNING: Failed to generate custom User-Agent: [error details]
```

### Metrics to Track
- Rate limit exception frequency
- User retry success rates
- Authentication flow completion rates

## Next Steps

1. **Deploy**: Implementation is ready for production
2. **Monitor**: Watch rate limiting patterns and user experience
3. **Optimize**: Adjust timeouts or messaging based on real usage
4. **Document**: Update user documentation about rate limiting

## Maintainer Feedback Addressed

> "Not true, we failed because of using generic User-Agent string from the requests library"
✅ **Fixed**: Auto-generated User-Agent following Wikimedia conventions

> "I think we should not retry the requests when encountering error 429"
✅ **Fixed**: No retry logic, immediate exception with user-friendly message

> "let's automatically compute it [User-Agent], to follow this convention"
✅ **Fixed**: Auto-computation using settings with proper format and fallback

This implementation fully addresses the maintainer's requirements while providing a robust, user-friendly solution for MediaWiki OAuth rate limiting.
