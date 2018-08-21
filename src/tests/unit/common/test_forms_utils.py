import pytest

from pretalx.common.forms.utils import get_help_text


@pytest.mark.parametrize('text,min_length,max_length,warning', (
    ('t', 1, 3, 't Please write between 1 and 3 characters.'),
    ('', 1, 3, 'Please write between 1 and 3 characters.'),
    ('t', 0, 3, 't Please write no more than 3 characters.'),
    ('t', 1, 0, 't Please write at least 1 characters.'),
))
def test_get_text_length_help_text(text, min_length, max_length, warning):
    assert get_help_text(text, min_length, max_length) == warning
