# MediaWiki OAuth Rate Limiting - User-Friendly Implementation (Issue #817)

## 📋 Problem Statement

The original MediaWiki OAuth implementation showed users exact retry times (e.g., "Try again in 127 seconds"), which created several UX problems:

- **User Pressure**: Exact countdown timers create anxiety and urgency
- **Synchronized Traffic**: Users retry exactly when told, creating traffic spikes  
- **Poor UX**: Technical language and precise times feel aggressive
- **Server Load**: Coordinated retries at exact times increase load

## ✅ Solution: Vague, User-Friendly Time Descriptions

### Key Changes

1. **Vague Time Ranges**: Instead of "127 seconds", users see "a couple of minutes"
2. **Friendly Language**: "Wikipedia login is temporarily busy" instead of "Rate limited"
3. **Natural Retries**: Users retry when convenient, not at exact times
4. **Internal Tracking**: Maintains exact times for debugging, but doesn't expose them

### Time Conversion Logic

```python
def _get_friendly_time_description(self, retry_after_seconds):
    """Convert exact times to user-friendly descriptions."""
    if retry_after_seconds is None:
        return "a few minutes"
    
    try:
        seconds = int(retry_after_seconds)
        if seconds <= 60:
            return "a minute"
        elif seconds <= 120:
            return "a couple of minutes"  
        elif seconds <= 300:
            return "a few minutes"
        elif seconds <= 600:
            return "several minutes"
        else:
            return "some time"
    except (ValueError, TypeError):
        return "a few minutes"
```

### User Message Examples

| Server Retry Time | User Sees |
|------------------|-----------|
| 30 seconds | "Please try again in a minute" |
| 120 seconds | "Please try again in a couple of minutes" |
| 300 seconds | "Please try again in a few minutes" |
| 600 seconds | "Please try again in several minutes" |

## 🎯 Benefits

### User Experience
- **Less Stressful**: No countdown pressure
- **More Professional**: Friendly, conversational language
- **Better Accessibility**: Clear, non-technical communication
- **Natural Behavior**: Users retry when convenient

### Technical Benefits
- **Distributed Load**: Retries spread over time windows
- **Reduced Spikes**: No synchronized retry attempts
- **Better Resilience**: System handles traffic more gracefully
- **Debugging Preserved**: Internal tracking for monitoring

## 📁 Files Modified

### Core Implementation
- **`src/pretix/plugins/socialauth/mediawiki_provider.py`**
  - `MediaWikiRateLimitException`: User-friendly exception with vague times
  - `RateLimitedOAuth2Client`: OAuth client with gentle rate limiting
  - `_get_friendly_time_description()`: Converts exact times to vague descriptions
  - `_handle_rate_limit_response()`: Shows user-friendly messages

### Configuration
- **`src/pretix/settings.py`**
  - Added MediaWiki OAuth configuration comments
  - User-Agent auto-generation settings

### Tests
- **`src/pretix/plugins/socialauth/tests/test_mediawiki_rate_limiting.py`**
  - Comprehensive test suite for user-friendly behavior
  - Tests for vague time descriptions
  - Verification that no exact times leak to users
  - Edge case handling

## 🧪 Testing

### Test Coverage
- ✅ Time conversion logic for all ranges
- ✅ User-friendly message generation
- ✅ No exact times in user messages
- ✅ Internal retry_after tracking preserved
- ✅ Edge cases (invalid times, missing headers)
- ✅ Integration with OAuth flow

### Example Test
```python
def test_rate_limit_with_user_friendly_message(self):
    """Test 429 responses show vague time descriptions."""
    mock_response.status_code = 429
    mock_response.headers = {'Retry-After': '120'}
    
    with self.assertRaises(MediaWikiRateLimitException) as cm:
        self.client.request('GET', 'https://test.com')
    
    # User sees vague description
    self.assertIn('a couple of minutes', str(cm.exception))
    # No exact time in user message
    self.assertNotIn('120', str(cm.exception))
    # But exact time tracked internally
    self.assertEqual(cm.exception.retry_after, 120)
```

## 🚀 Implementation Status

### ✅ Completed
- [x] User-friendly time conversion logic
- [x] Vague time descriptions instead of exact times
- [x] Gentle, professional error messages
- [x] Comprehensive test suite
- [x] Internal retry tracking for debugging
- [x] Documentation and examples

### 🎯 Ready for Deployment
- All code follows FOSSASIA patterns
- Comprehensive test coverage
- Backward compatible
- No breaking changes
- Production ready

## 📈 Expected Impact

### User Metrics
- **Reduced Bounce Rate**: Users less likely to abandon login
- **Better Retention**: More pleasant experience during high traffic
- **Accessibility**: Clearer communication for all users

### System Metrics  
- **Smoother Traffic**: Retry attempts distributed over time
- **Reduced Peaks**: No synchronized retry spikes
- **Better Resilience**: System handles load more gracefully

## 🎉 Summary

This implementation successfully addresses Issue #817 by:

1. **Removing user pressure** from exact countdown timers
2. **Providing gentle guidance** with vague time descriptions  
3. **Improving system resilience** through distributed retry patterns
4. **Maintaining debugging capability** with internal time tracking
5. **Following FOSSASIA standards** for code quality and testing

The solution balances user experience with technical requirements, creating a more professional and user-friendly MediaWiki OAuth integration for eventyay-tickets.
