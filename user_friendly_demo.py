#!/usr/bin/env python3
"""
Demonstration script for user-friendly MediaWiki OAuth rate limiting (Issue #817).

This script shows how the new implementation provides vague, user-friendly
time descriptions instead of exact retry times to avoid rushing users.
"""

def demonstrate_user_friendly_times():
    """Demonstrate the user-friendly time conversion logic."""
    
    def get_friendly_time_description(retry_after_seconds):
        """
        Convert retry time to user-friendly vague description.
        This matches the logic in RateLimitedOAuth2Client._get_friendly_time_description()
        """
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
    
    print("🎯 MediaWiki OAuth Rate Limiting - User-Friendly Time Descriptions")
    print("=" * 70)
    print()
    
    print("📋 Issue #817: Replace specific retry times with vague descriptions")
    print("Goal: Don't rush users with exact times, provide gentle guidance")
    print()
    
    # Test various retry times
    test_cases = [
        (30, "30 seconds"),
        (60, "1 minute"), 
        (90, "1.5 minutes"),
        (120, "2 minutes"),
        (180, "3 minutes"),
        (300, "5 minutes"),
        (450, "7.5 minutes"),
        (600, "10 minutes"),
        (900, "15 minutes"),
        (1200, "20 minutes"),
        (None, "No time given"),
        ("invalid", "Invalid input"),
    ]
    
    print("🔄 Time Conversion Examples:")
    print("-" * 50)
    print(f"{'Actual Time':<15} {'User Sees':<20} {'Benefits'}")
    print("-" * 50)
    
    for actual_time, description in test_cases:
        friendly_desc = get_friendly_time_description(actual_time)
        
        if actual_time == 30:
            benefit = "No pressure from exact countdown"
        elif actual_time == 90:
            benefit = "Rounds to friendly language"
        elif actual_time == 300:
            benefit = "Avoids specific 5-minute timer"
        elif actual_time == 900:
            benefit = "Gentle for longer waits"
        elif actual_time is None:
            benefit = "Graceful fallback"
        else:
            benefit = "User-friendly phrasing"
            
        print(f"{description:<15} {friendly_desc:<20} {benefit}")
    
    print()
    print("✨ Benefits of Vague Time Descriptions:")
    print("  • Reduces user anxiety from countdown timers")
    print("  • Prevents users from refreshing exactly at retry time")
    print("  • More forgiving and professional user experience")
    print("  • Aligns with modern UX best practices")
    print("  • Reduces server load from synchronized retries")
    print()
    
    print("📱 Example User Messages:")
    print("-" * 30)
    
    example_messages = [
        ("30 seconds", "Wikipedia login is temporarily busy. Please try again in a minute."),
        ("120 seconds", "Wikipedia login is temporarily busy. Please try again in a couple of minutes."),
        ("300 seconds", "Wikipedia login is temporarily busy. Please try again in a few minutes."),
        ("600 seconds", "Wikipedia login is temporarily busy. Please try again in several minutes."),
    ]
    
    for actual, message in example_messages:
        print(f"  ⏱️  Server says: {actual}")
        print(f"  👤 User sees: {message}")
        print()

def demonstrate_implementation_benefits():
    """Show the benefits of the new implementation."""
    
    print("🏆 Implementation Benefits for Issue #817:")
    print("=" * 50)
    print()
    
    print("❌ BEFORE (Problematic):")
    print("  • 'Rate limited. Try again in 127 seconds.'")
    print("  • Users count down and retry exactly at 127 seconds")
    print("  • Creates synchronized traffic spikes")
    print("  • Feels aggressive and demanding")
    print("  • Technical language confuses users")
    print()
    
    print("✅ AFTER (User-Friendly):")
    print("  • 'Wikipedia login is temporarily busy. Please try again in a couple of minutes.'")
    print("  • Users retry naturally when convenient")
    print("  • Spreads out retry attempts over time")
    print("  • Feels gentle and professional")
    print("  • Clear, non-technical language")
    print()
    
    print("🎯 Key Improvements:")
    print("  1. Vague time ranges instead of exact seconds")
    print("  2. Friendly language that doesn't pressure users")
    print("  3. Natural distribution of retry attempts")
    print("  4. Better user experience during high traffic")
    print("  5. Maintains internal tracking for debugging")
    print()

if __name__ == "__main__":
    demonstrate_user_friendly_times()
    print()
    demonstrate_implementation_benefits()
    print()
    print("🎉 Ready for implementation in eventyay-tickets!")
    print("   File: src/pretix/plugins/socialauth/mediawiki_provider.py")
    print("   Tests: src/pretix/plugins/socialauth/tests/test_mediawiki_rate_limiting.py")
