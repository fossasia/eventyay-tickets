from django import template

register = template.Library()

@register.filter
def split(value, delimiter=','):
    """
    Usage: {{ value|split:"," }}
    """
    if not isinstance(value, str):
        return []
    return [v.strip() for v in value.split(delimiter)]
