from datetime import date

import pytest
from django.utils import translation

from pretalx.common.utils import daterange


def test_same_day_german():
    with translation.override('de'):
        df = date(2003, 2, 1)
        assert daterange(df, df) == "1. Februar 2003"


def test_same_day_english():
    with translation.override('en'):
        df = date(2003, 2, 1)
        assert daterange(df, df) == "Feb. 1st, 2003"


def test_same_day_spanish():
    with translation.override('es'):
        df = date(2003, 2, 1)
        assert daterange(df, df) == "1 de Febrero de 2003"


def test_same_month_german():
    with translation.override('de'):
        df = date(2003, 2, 1)
        dt = date(2003, 2, 3)
        assert daterange(df, dt) == "1.–3. Februar 2003"


def test_same_month_english():
    with translation.override('en'):
        df = date(2003, 2, 1)
        dt = date(2003, 2, 3)
        assert daterange(df, dt) == "Feb. 1st – 3rd, 2003"


def test_same_month_spanish():
    with translation.override('es'):
        df = date(2003, 2, 1)
        dt = date(2003, 2, 3)
        assert daterange(df, dt) == "1 - 3 de Febrero de 2003"


def test_same_year_german():
    with translation.override('de'):
        df = date(2003, 2, 1)
        dt = date(2003, 4, 3)
        assert daterange(df, dt) == "1. Februar – 3. April 2003"


def test_same_year_english():
    with translation.override('en'):
        df = date(2003, 2, 1)
        dt = date(2003, 4, 3)
        assert daterange(df, dt) == "Feb. 1st – April 3rd, 2003"


def test_different_dates_spanish():
    with translation.override('es'):
        df = date(2003, 2, 1)
        dt = date(2005, 4, 3)
        assert daterange(df, dt) == "1 de Febrero de 2003 – 3 de Abril de 2005"


def test_different_dates_german():
    with translation.override('de'):
        df = date(2003, 2, 1)
        dt = date(2005, 4, 3)
        assert daterange(df, dt) == "1. Februar 2003 – 3. April 2005"


def test_different_dates_english():
    with translation.override('en'):
        df = date(2003, 2, 1)
        dt = date(2005, 4, 3)
        assert daterange(df, dt) == "Feb. 1, 2003 – April 3, 2005"


@pytest.mark.parametrize('path,expected', (
    ('foo.bar', 'foo_aaaaaaa.bar'),
    ('foo_.bar', 'foo__aaaaaaa.bar'),
    ('foo', 'foo_aaaaaaa'),
    ('/home/foo.bar', '/home/foo_aaaaaaa.bar'),
    ('/home/foo_.bar', '/home/foo__aaaaaaa.bar'),
    ('/home/foo', '/home/foo_aaaaaaa'),
    ('home/foo.bar', 'home/foo_aaaaaaa.bar'),
    ('home/foo_.bar', 'home/foo__aaaaaaa.bar'),
    ('home/foo', 'home/foo_aaaaaaa'),
))
def test_path_with_hash(path, expected, monkeypatch):
    monkeypatch.setattr('pretalx.common.utils.get_random_string', lambda x: 'aaaaaaa')
    from pretalx.common.utils import path_with_hash
    assert path_with_hash(path) == expected
