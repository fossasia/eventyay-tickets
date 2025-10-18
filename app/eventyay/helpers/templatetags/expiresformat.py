from django import template
from django.utils.timezone import get_default_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from eventyay.base.i18n import LazyExpiresDate

register = template.Library()


@register.filter
def format_expires(order):
    try:
        tz = ZoneInfo(order.event.timezone)
    except ZoneInfoNotFoundError:
        tz = get_default_timezone()
    return LazyExpiresDate(order.expires.astimezone(tz))
