import datetime as dt

from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder


def serialize_duration(minutes):
    duration = dt.timedelta(minutes=minutes)
    days = duration.days
    hours = int(duration.total_seconds() // 3600 - days * 24)
    minutes = int(duration.seconds // 60 % 60)
    fmt = f'{minutes:02}'
    if hours or days:
        fmt = f'{hours:02}:{fmt}'
        if days:
            fmt = f'{days}:{fmt}'
    else:
        fmt = f'00:{fmt}'
    return fmt


class I18nStrJSONEncoder(I18nJSONEncoder):
    def default(self, obj):
        if isinstance(obj, LazyI18nString):
            return str(obj)
        return super().default(obj)
