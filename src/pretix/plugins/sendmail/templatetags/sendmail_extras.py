from django import template

register = template.Library()

@register.filter
def to_user_emails(to_users):
    """
    Extracts emails from to_users and returns a comma-separated string.
    """
    if isinstance(to_users, list):
        return ", ".join([u.get("email", "") for u in to_users if u.get("email")])
    return ""
