from typing import Optional
from urllib.parse import quote

from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag
def oauth_login_url(next_url: Optional[str] = None) -> str:
    """
    Generate the OAuth login URL with an optional next parameter.
    Usage: {% oauth_login_url next_url %}
    """
    base_url = reverse("eventyay_common:oauth2_provider.login")
    if next_url:
        return f"{base_url}?next={quote(next_url)}"
    return base_url


@register.simple_tag
def register_account_url(next_url: Optional[str] = None) -> str:
    """
    Generate the registration URL with an optional next parameter.
    Usage: {% register_account_url next_url %}
    """
    base_url = reverse("eventyay_common:register.account")
    if next_url:
        return f"{base_url}?next={quote(next_url)}"
    return base_url
