import pytest

from pretalx.common.templatetags.copyable import copyable
from pretalx.common.templatetags.rich_text import rich_text
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


@pytest.mark.parametrize('text,richer_text', (
    ('foo.notatld', 'foo.notatld'),
    ('foo.com', '<a href="http://foo.com" rel="nofollow">foo.com</a>'),
    ('foo@bar.com', '<a href="mailto:foo@bar.com">foo@bar.com</a>'),
    ('chaos.social', '<a href="http://chaos.social" rel="nofollow">chaos.social</a>'),
))
def test_common_templatetag_rich_text(text, richer_text):
    assert rich_text(text) == f'<p>{richer_text}</p>'


@pytest.mark.parametrize('value,copy', (
    ('"foo', '"foo'),
    ('foo', """
    <span data-destination="foo"
            class="copyable-text"
            data-toggle="tooltip"
            data-placement="top"
            title="Copy"
    >
        foo
    </span>""")
))
def test_common_templatetag_copyable(value, copy):
    assert copyable(value) == copy
