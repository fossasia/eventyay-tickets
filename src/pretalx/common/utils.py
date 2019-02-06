from django.template.defaultfilters import date as _date
from django.utils.translation import get_language, ugettext_lazy as _


def daterange(date_from, date_to):
    language = get_language()

    if language.startswith("de"):
        if (
            date_from.year == date_to.year
            and date_from.month == date_to.month
            and date_from.day == date_to.day
        ):
            return str(_date(date_from, "j. F Y"))
        elif date_from.year == date_to.year and date_from.month == date_to.month:
            return "{}.–{}".format(_date(date_from, "j"), _date(date_to, "j. F Y"))
        elif date_from.year == date_to.year:
            return "{} – {}".format(_date(date_from, "j. F"), _date(date_to, "j. F Y"))
    elif language.startswith("en"):
        if (
            date_from.year == date_to.year
            and date_from.month == date_to.month
            and date_from.day == date_to.day
        ):
            return str(_date(date_from, "N jS, Y"))
        elif date_from.year == date_to.year and date_from.month == date_to.month:
            return "{} – {}".format(_date(date_from, "N jS"), _date(date_to, "jS, Y"))
        elif date_from.year == date_to.year:
            return "{} – {}".format(_date(date_from, "N jS"), _date(date_to, "N jS, Y"))
    elif language.startswith("es"):
        if (
            date_from.year == date_to.year
            and date_from.month == date_to.month
            and date_from.day == date_to.day
        ):
            return "{}".format(_date(date_from, "DATE_FORMAT"))
        elif date_from.year == date_to.year and date_from.month == date_to.month:
            return "{} - {} de {} de {}".format(
                _date(date_from, "j"),
                _date(date_to, "j"),
                _date(date_to, "F"),
                _date(date_to, "Y"),
            )
        elif date_from.year == date_to.year:
            return "{} de {} - {} de {} de {}".format(
                _date(date_from, "j"),
                _date(date_from, "F"),
                _date(date_to, "j"),
                _date(date_to, "F"),
                _date(date_to, "Y"),
            )

    return _("{date_from} – {date_to}").format(
        date_from=_date(date_from, "DATE_FORMAT"), date_to=_date(date_to, "DATE_FORMAT")
    )
