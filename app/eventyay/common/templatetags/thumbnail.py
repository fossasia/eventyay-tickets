from django import template

from eventyay.common.image import get_thumbnail

register = template.Library()


@register.filter
def thumbnail(field, size):
    try:
        return get_thumbnail(field, size).url
    except Exception:
        return field.url if hasattr(field, 'url') else None
