from django import template
from urllib.parse import urlencode

register = template.Library()


@register.simple_tag
def append_next(next_url=None):
    if next_url and next_url.strip():
        return f'?next={urlencode({"next": next_url})}'
    return ''
