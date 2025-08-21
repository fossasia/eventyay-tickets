import html
import re
import urllib.parse
from copy import copy
from functools import partial

import bleach
import markdown
from bleach import DEFAULT_CALLBACKS
from bleach.linkifier import build_email_re, build_url_re
from django import template
from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe

try:
    from publicsuffixlist import PublicSuffixList
    TLD_SET = sorted({suffix.rsplit(".")[-1] for suffix in PublicSuffixList()._publicsuffix}, reverse=True)
except ImportError:
    from tlds import tld_set
    TLD_SET = sorted(tld_set, key=len, reverse=True)

from i18nfield.strings import LazyI18nString
from eventyay.common.views.redirect import safelink as sl

register = template.Library()

ALLOWED_TAGS = {
    "a", "abbr", "acronym", "b", "blockquote", "br", "code", "del", "div",
    "em", "hr", "i", "li", "ol", "strong", "ul", "p", "pre", "span", "table",
    "tbody", "thead", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
}

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "class"],
    "abbr": ["title"],
    "acronym": ["title"],
    "table": ["width"],
    "td": ["width", "align"],
    "div": ["class"],
    "p": ["class"],
    "span": ["class", "title"],
}

ALLOWED_PROTOCOLS = {"http", "https", "mailto", "tel"}

URL_RE = build_url_re(tlds=TLD_SET)
EMAIL_RE = build_email_re(tlds=TLD_SET)


def link_callback(attrs, is_new, safelink=True):
    url = attrs.get((None, "href"), "/")
    if url.startswith("mailto:") or url.startswith("tel:") or url_has_allowed_host_and_scheme(url, allowed_hosts=None):
        return attrs
    attrs[None, "target"] = "_blank"
    attrs[None, "rel"] = "noopener"
    if safelink:
        url = html.unescape(url)
        attrs[None, "href"] = sl(url)
    else:
        url = html.unescape(url)
        attrs[None, "href"] = urllib.parse.urljoin(settings.SITE_URL, url)
    return attrs

safelink_callback = partial(link_callback, safelink=True)
abslink_callback = partial(link_callback, safelink=False)

CLEANER = bleach.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    filters=[
        partial(
            bleach.linkifier.LinkifyFilter,
            url_re=URL_RE,
            parse_email=True,
            email_re=EMAIL_RE,
            skip_tags={"pre", "code"},
            callbacks=DEFAULT_CALLBACKS + [safelink_callback],
        )
    ],
)

ABSLINK_CLEANER = bleach.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    filters=[
        partial(
            bleach.linkifier.LinkifyFilter,
            url_re=URL_RE,
            parse_email=True,
            email_re=EMAIL_RE,
            skip_tags={"pre", "code"},
            callbacks=DEFAULT_CALLBACKS + [abslink_callback],
        )
    ],
)

NO_LINKS_CLEANER = bleach.Cleaner(
    tags=copy(ALLOWED_TAGS) - {"a"},
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    strip=True,
)

STRIKETHROUGH_RE = "(~{2})(.+?)(~{2})"

def markdown_compile_email(source):
    linker = bleach.Linker(
        url_re=URL_RE,
        email_re=EMAIL_RE,
        callbacks=DEFAULT_CALLBACKS + [truelink_callback, abslink_callback],
        parse_email=True,
    )
    return linker.linkify(
        bleach.clean(
            markdown.markdown(
                source,
                extensions=[
                    'markdown.extensions.sane_lists',
                    #  'markdown.extensions.nl2br' # disabled for backwards-compatibility
                ],
            ),
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            protocols=ALLOWED_PROTOCOLS,
        )
    )

class StrikeThroughExtension(markdown.Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            markdown.inlinepatterns.SimpleTagPattern(STRIKETHROUGH_RE, "del"),
            "strikethrough",
            200,
        )

md = markdown.Markdown(
    extensions=[
        "markdown.extensions.nl2br",
        "markdown.extensions.sane_lists",
        "markdown.extensions.tables",
        "markdown.extensions.fenced_code",
        "markdown.extensions.codehilite",
        "markdown.extensions.md_in_html",
        StrikeThroughExtension(),
    ]
)


def render_markdown(text: str, cleaner=CLEANER) -> str:
    if not text:
        return ""
    body_md = cleaner.clean(md.reset().convert(str(text)))
    return mark_safe(body_md)


def render_markdown_abslinks(text: str) -> str:
    return render_markdown(text, cleaner=ABSLINK_CLEANER)


@register.filter
def rich_text(text: str):
    return render_markdown(text, cleaner=CLEANER)


@register.filter
def rich_text_without_links(text: str):
    return render_markdown(text, cleaner=NO_LINKS_CLEANER)


@register.filter
def rich_text_snippet(text: str):
    return render_markdown(text, cleaner=ABSLINK_CLEANER)


@register.filter
def append_colon(text: LazyI18nString) -> str:
    text = str(text).strip()
    if not text:
        return ""
    return text if text[-1] in [".", "!", "?", ":", ";"] else f"{text}:"
