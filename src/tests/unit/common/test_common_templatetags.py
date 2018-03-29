import pytest

from pretalx.common.templatetags.times import times


@pytest.mark.parametrize('number,output', (
    (1, 'once'),
    (2, 'twice'),
    (3, '3 times'),
    (None, ''),
    (0, '0 times'),
    ('1', 'once'),
    ('2', 'twice'),
    ('3', '3 times'),
))
def test_common_templatetag_times(number, output):
    assert times(number) == output
