from django import template

from eventyay.base.i18n import LazyExpiresDate


register = template.Library()


@register.filter
def format_expires(order):
    return LazyExpiresDate(order.expires.astimezone(order.event.timezone))
