from django.utils.formats import get_format


def get_day_month_date_format() -> str:
    return get_format('SHORT_DATE_FORMAT', use_l10n=True).strip('Y').strip('.-/,')


def get_notification_date_format() -> str:
    """Call from correct locale context!"""
    return get_day_month_date_format() + ', ' + get_format('TIME_FORMAT')
