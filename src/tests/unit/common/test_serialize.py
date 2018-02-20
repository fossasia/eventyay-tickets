import pytest

from pretalx.common.serialize import serialize_duration


@pytest.mark.parametrize('minutes,result', (
    (1, '00:01'),
    (0, '00:00'),
    (10, '00:10'),
    (30, '00:30'),
    (60, '01:00'),
    (60 * 1.5, '01:30'),
    (60 * 2, '02:00'),
    (60 * 2.5, '02:30'),
    (60 * 12, '12:00'),
    (60 * 24, '1:00:00'),
    (60 * (24 + 1.5), '1:01:30'),
))
def test_serialize_duration(minutes, result):
    assert serialize_duration(minutes=minutes) == result
