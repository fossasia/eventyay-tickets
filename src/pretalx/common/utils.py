from django.template.defaultfilters import date as _date
from django.utils.translation import get_language, ugettext_lazy as _
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder


def daterange_de(date_from, date_to):
    if (
        date_from.year == date_to.year
        and date_from.month == date_to.month
        and date_from.day == date_to.day
    ):
        return str(_date(date_from, "j. F Y"))
    if date_from.year == date_to.year and date_from.month == date_to.month:
        return "{}.–{}".format(_date(date_from, "j"), _date(date_to, "j. F Y"))
    if date_from.year == date_to.year:
        return "{} – {}".format(_date(date_from, "j. F"), _date(date_to, "j. F Y"))


def daterange_en(date_from, date_to):
    if (
        date_from.year == date_to.year
        and date_from.month == date_to.month
        and date_from.day == date_to.day
    ):
        return str(_date(date_from, "N jS, Y"))
    if date_from.year == date_to.year and date_from.month == date_to.month:
        return "{} – {}".format(_date(date_from, "N jS"), _date(date_to, "jS, Y"))
    if date_from.year == date_to.year:
        return "{} – {}".format(_date(date_from, "N jS"), _date(date_to, "N jS, Y"))


def daterange_es(date_from, date_to):
    if (
        date_from.year == date_to.year
        and date_from.month == date_to.month
        and date_from.day == date_to.day
    ):
        return "{}".format(_date(date_from, "DATE_FORMAT"))
    if date_from.year == date_to.year and date_from.month == date_to.month:
        return "{} - {} de {} de {}".format(
            _date(date_from, "j"),
            _date(date_to, "j"),
            _date(date_to, "F"),
            _date(date_to, "Y"),
        )
    if date_from.year == date_to.year:
        return "{} de {} - {} de {} de {}".format(
            _date(date_from, "j"),
            _date(date_from, "F"),
            _date(date_to, "j"),
            _date(date_to, "F"),
            _date(date_to, "Y"),
        )


def daterange(date_from, date_to):
    result = None
    language = get_language()

    if language.startswith("de"):
        result = daterange_de(date_from, date_to)
    elif language.startswith("en"):
        result = daterange_en(date_from, date_to)
    elif language.startswith("es"):
        result = daterange_es(date_from, date_to)

    return result or _("{date_from} – {date_to}").format(
        date_from=_date(date_from, "DATE_FORMAT"), date_to=_date(date_to, "DATE_FORMAT")
    )


class I18nStrJSONEncoder(I18nJSONEncoder):
    def default(self, obj):
        if isinstance(obj, LazyI18nString):
            return str(obj)
        return super().default(obj)
