from datetime import datetime

from django import template
from django.template.defaultfilters import date as date_filter
from django.utils.html import format_html
from django.utils.timezone import get_current_timezone

register = template.Library()


def render_time(time, fmt):
    tz = get_current_timezone()
    time = time.astimezone(tz)
    html_iso = date_filter(time, 'Y-m-d H:i')
    return format_html(
        '<time datetime="{}" date-timezone="{}" data-isodatetime="{}" title="{}" data-toggle="tooltip" data-placement="bottom">{}</time>',
        html_iso,
        tz,
        time.isoformat(),
        tz,
        date_filter(time, fmt),
    )


@register.filter()
def datetimerange(start: datetime, end: datetime):
    if not start and not end:
        return ''
    if not end:
        return render_time(start, 'SHORT_DATETIME_FORMAT')
    tz = get_current_timezone()
    start = start.astimezone(tz)
    end = end.astimezone(tz)
    if start.year == end.year and start.month == end.month and start.day == end.day:
        start_format = format_html(
            '{} {}',
            date_filter(start, 'SHORT_DATE_FORMAT'),
            render_time(start, 'TIME_FORMAT'),
        )
        end_format = render_time(end, 'TIME_FORMAT')
        separator = '–'
    else:
        start_format = render_time(start, 'SHORT_DATETIME_FORMAT')
        end_format = render_time(end, 'SHORT_DATETIME_FORMAT')
        separator = ' – '
    return format_html(
        '<span class="timerange-block">{}{}{}</span>',
        start_format,
        separator,
        end_format,
    )
