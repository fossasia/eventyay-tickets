def get_or_create_email_for_wikimedia_user(username, email=None, user_id=None):
    """
    Generate an email for Wikimedia users.
    
    Sanitizes username to ensure valid email format and uniqueness.
    Falls back to user ID if username is empty or invalid.
    
    Args:
        username (str): Wikimedia username
        email (str): Email from Wikimedia profile (can be None)
        user_id: Wikimedia user ID for uniqueness and fallback
    
    Returns:
        str: Email address
    """
    if email and email.strip():
        return email
    
    # Sanitize username: lowercase, strip, replace whitespace with dots, remove invalid chars
    if username:
        sanitized = username.lower().strip()
        sanitized = sanitized.replace(' ', '.').replace('_', '.')
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '.-')
        while '..' in sanitized:
            sanitized = sanitized.replace('..', '.')
        sanitized = sanitized.strip('.')
    else:
        sanitized = None
    
    # If sanitized username is empty or invalid, use user ID as fallback
    if sanitized:
        if user_id:
            return f"{sanitized}.{user_id}@wikimedia.local"
        return f"{sanitized}@wikimedia.local"
    else:
        # Fallback: use Wikimedia user ID only
        if user_id:
            return f"wm.{user_id}@wikimedia.local"
        else:
            return "wikimedia.user@wikimedia.local"


def is_placeholder_email(email):
    """
    Check if an email is a placeholder (non-routable) Wikimedia address.
    These emails should never have messages sent to them.
    
    Args:
        email (str): Email address to check
    
    Returns:
        bool: True if the email is a placeholder Wikimedia email
    """
    if not email:
        return False
    return email.endswith('@wikimedia.local')


def is_wikimedia_user(user):
    """
    Check if user is authenticated via Wikimedia OAuth

    Args:
        user: Django User instance

    Returns:
        bool: True if user is a Wikimedia OAuth user
    """
    return user.is_authenticated and getattr(user, 'is_wikimedia_user', False)
