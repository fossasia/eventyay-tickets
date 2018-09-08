import pytest

from pretalx.common.templatetags.times import times
from pretalx.common.templatetags.xmlescape import xmlescape


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


@pytest.mark.parametrize('input_,output', (
    ('i am a normal string ??!!$%/()=?', 'i am a normal string ??!!$%/()=?'),
    ('<', '&lt;'),
    ('>', '&gt;'),
    ('"', '&quot;'),
    ("'", '&apos;'),
    ('&', '&amp;'),
    ('a\aa', 'aa'),
    ('ä', '&#228;'),
))
def test_common_templatetag_xmlescape(input_, output):
    assert xmlescape(input_) == output
