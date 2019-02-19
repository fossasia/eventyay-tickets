import pytest

from pretalx.common.forms.utils import get_help_text


@pytest.mark.parametrize('text,min_length,max_length,_type,warning', (
    ('t', 1, 3, 'chars', 't Please write between 1 and 3 characters.'),
    ('', 1, 3, 'chars', 'Please write between 1 and 3 characters.'),
    ('t', 0, 3, 'chars', 't Please write at most 3 characters.'),
    ('t', 1, 0, 'chars', 't Please write at least 1 characters.'),
    ('t', 1, 3, 'words', 't Please write between 1 and 3 words.'),
    ('', 1, 3, 'words', 'Please write between 1 and 3 words.'),
    ('t', 0, 3, 'words', 't Please write at most 3 words.'),
    ('t', 1, 0, 'words', 't Please write at least 1 words.'),
))
def test_get_text_length_help_text(text, min_length, max_length, _type, warning):
    assert get_help_text(text, min_length, max_length, _type) == warning
