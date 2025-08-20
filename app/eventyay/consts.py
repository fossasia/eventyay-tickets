import zoneinfo


TIMEZONE_CHOICES = sorted([tz for tz in zoneinfo.available_timezones() if not tz.startswith('Etc/') and tz != 'localtime'])
