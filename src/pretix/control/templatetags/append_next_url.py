from urllib.parse import urlencode

from django import template

register = template.Library()


@register.simple_tag
def append_next(next_url=None):
    if next_url and next_url.strip():
        return f"?{urlencode({'next': next_url})}"
    return ""
