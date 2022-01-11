import pytest
from django_scopes import scope

from pretalx.common.templatetags.copyable import copyable
from pretalx.common.templatetags.html_signal import html_signal
from pretalx.common.templatetags.rich_text import rich_text
from pretalx.common.templatetags.times import times
from pretalx.common.templatetags.url_replace import url_replace
from pretalx.common.templatetags.xmlescape import xmlescape


@pytest.mark.parametrize(
    "number,output",
    (
        (1, "once"),
        (2, "twice"),
        (3, "3 times"),
        (None, ""),
        (0, "0 times"),
        ("1", "once"),
        ("2", "twice"),
        ("3", "3 times"),
    ),
)
def test_common_templatetag_times(number, output):
    assert times(number) == output


@pytest.mark.parametrize(
    "input_,output",
    (
        ("i am a normal string ??!!$%/()=?", "i am a normal string ??!!$%/()=?"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&apos;"),
        ("&", "&amp;"),
        ("a\aa", "aa"),
        ("ä", "&#228;"),
    ),
)
def test_common_templatetag_xmlescape(input_, output):
    assert xmlescape(input_) == output


@pytest.mark.parametrize(
    "text,richer_text",
    (
        ("foo.notatld", "foo.notatld"),
        (
            "foo.com",
            '<a href="http://foo.com" rel="nofollow" target="_blank">foo.com</a>',
        ),
        ("foo@bar.com", '<a href="mailto:foo@bar.com" target="_blank">foo@bar.com</a>'),
        (
            "chaos.social",
            '<a href="http://chaos.social" rel="nofollow" target="_blank">chaos.social</a>',
        ),
    ),
)
def test_common_templatetag_rich_text(text, richer_text):
    assert rich_text(text) == f"<p>{richer_text}</p>"


@pytest.mark.parametrize(
    "value,copy",
    (
        ('"foo', '"foo'),
        (
            "foo",
            """
    <span data-destination="foo"
            class="copyable-text"
            data-toggle="tooltip"
            data-placement="top"
            title="Copy"
    >
        foo
    </span>""",
        ),
    ),
)
def test_common_templatetag_copyable(value, copy):
    assert copyable(value) == copy


@pytest.mark.django_db
@pytest.mark.parametrize("slug", (True, False))
@pytest.mark.parametrize("signal", ("html_head", "html_above_profile_page"))
def test_html_signal(event, slug, signal):
    with scope(event=event):
        if slug:
            event.slug = "ignore_signal"
        event.plugins = "tests"
        event.save()
        result = html_signal(
            f"pretalx.cfp.signals.{signal}", sender=event, request=None
        )
        assert bool(result) is not slug


class MockEncodeDict(dict):
    def urlencode(self, **kwargs):
        return self

    def copy(self):
        return self


class FakeRequest:
    def __init__(self, get):
        self.GET = MockEncodeDict(get)


@pytest.mark.parametrize(
    "get,replace,response",
    (
        ({"foo": "bar"}, ["baz", "bar"], {"foo": "bar", "baz": "bar"}),
        ({}, ["baz", "bar"], {"baz": "bar"}),
        ({"foo": "bar"}, ["foo", "baz"], {"foo": "baz"}),
        ({"foo": "bar"}, ["foo", ""], {}),
        ({"foo": "bar"}, ["bar", ""], {"foo": "bar"}),
    ),
)
def test_url_replace(get, replace, response):
    assert url_replace(FakeRequest(get), *replace) == response
