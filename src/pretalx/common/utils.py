import contextlib
import os

from django.db import transaction
from django.template.defaultfilters import date as _date
from django.utils.crypto import get_random_string
from django.utils.translation import get_language, gettext_lazy as _
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


def path_with_hash(name):
    dir_name, file_name = os.path.split(name)
    file_root, file_ext = os.path.splitext(file_name)
    random = get_random_string(7)
    return os.path.join(dir_name, f"{file_root}_{random}{file_ext}")


@contextlib.contextmanager
def rolledback_transaction():
    """
    This context manager runs your code in a database transaction that will be rolled back in the end.
    This can come in handy to simulate the effects of a database operation that you do not actually
    want to perform.
    Note that rollbacks are a very slow operation on most database backends. Also, long-running
    transactions can slow down other operations currently running and you should not use this
    in a place that is called frequently.
    """

    class DummyRollbackException(Exception):
        pass

    try:
        with transaction.atomic():
            yield
            raise DummyRollbackException()
    except DummyRollbackException:
        pass
    else:
        raise Exception('Invalid state, should have rolled back.')
