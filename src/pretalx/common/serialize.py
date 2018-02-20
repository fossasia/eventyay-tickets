from datetime import timedelta


def serialize_duration(minutes):
    duration = timedelta(minutes=minutes)
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
