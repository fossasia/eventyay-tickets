from datetime import date

import pytest
from django.utils import translation
from i18nfield.strings import LazyI18nString

from pretalx.common.utils import I18nStrJSONEncoder, daterange, safe_filename


@pytest.mark.parametrize(
    "locale,start,end,result",
    (
        ("de", date(2003, 2, 1), date(2003, 2, 1), "1. Februar 2003"),
        ("en", date(2003, 2, 1), date(2003, 2, 1), "Feb. 1st, 2003"),
        ("es", date(2003, 2, 1), date(2003, 2, 1), "1 de febrero de 2003"),
        ("de", date(2003, 2, 1), date(2003, 2, 3), "1.–3. Februar 2003"),
        ("en", date(2003, 2, 1), date(2003, 2, 3), "Feb. 1st – 3rd, 2003"),
        ("es", date(2003, 2, 1), date(2003, 2, 3), "1 - 3 de febrero de 2003"),
        ("de", date(2003, 2, 1), date(2003, 4, 3), "1. Februar – 3. April 2003"),
        ("en", date(2003, 2, 1), date(2003, 4, 3), "Feb. 1st – April 3rd, 2003"),
        ("es", date(2003, 2, 1), date(2003, 4, 3), "1 de febrero - 3 de abril de 2003"),
        ("de", date(2003, 2, 1), date(2005, 4, 3), "1. Februar 2003 – 3. April 2005"),
        ("en", date(2003, 2, 1), date(2005, 4, 3), "Feb. 1, 2003 – April 3, 2005"),
        (
            "es",
            date(2003, 2, 1),
            date(2005, 4, 3),
            "1 de febrero de 2003 -3 de abril de 2005",
        ),
    ),
)
def test_daterange(locale, start, end, result):
    with translation.override(locale):
        assert daterange(start, end) == result


@pytest.mark.parametrize(
    "path,expected",
    (
        ("foo.bar", "foo_aaaaaaa.bar"),
        ("foo_.bar", "foo__aaaaaaa.bar"),
        ("foo", "foo_aaaaaaa"),
        ("/home/foo.bar", "/home/foo_aaaaaaa.bar"),
        ("/home/foo_.bar", "/home/foo__aaaaaaa.bar"),
        ("/home/foo", "/home/foo_aaaaaaa"),
        ("home/foo.bar", "home/foo_aaaaaaa.bar"),
        ("home/foo_.bar", "home/foo__aaaaaaa.bar"),
        ("home/foo", "home/foo_aaaaaaa"),
    ),
)
def test_path_with_hash(path, expected, monkeypatch):
    monkeypatch.setattr("pretalx.common.utils.get_random_string", lambda x: "aaaaaaa")
    from pretalx.common.utils import path_with_hash

    assert path_with_hash(path) == expected


@pytest.mark.parametrize(
    "filename,expected",
    (
        ("ö", "o"),
        ("å", "a"),
        ("ø", ""),
        ("α", ""),
    ),
)
def test_safe_filename(filename, expected):
    assert safe_filename(filename) == expected


@pytest.mark.django_db
def test_json_encoder_inheritance(event):
    assert I18nStrJSONEncoder().default(event) == {"id": event.pk, "type": "Event"}


@pytest.mark.django_db
def test_json_encoder_i18nstr(event):
    assert (
        I18nStrJSONEncoder().default(LazyI18nString({"en": "foo", "de": "bar"}))
        == "foo"
    )
