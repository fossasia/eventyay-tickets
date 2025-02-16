from copy import copy
from functools import partial

import bleach
import markdown
from django import template
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from publicsuffixlist import PublicSuffixList

from pretalx.common.views.redirect import safelink as sl

register = template.Library()

ALLOWED_TAGS = {
    "a",  # Keep in first position for link_cleaner
    "abbr",
    "acronym",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "hr",
    "i",
    "li",
    "ol",
    "strong",
    "ul",
    "p",
    "pre",
    "span",
    "table",
    "tbody",
    "thead",
    "tr",
    "td",
    "th",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "abbr": ["title"],
    "acronym": ["title"],
    "table": ["width"],
    "td": ["width", "align"],
    "div": ["class"],
    "p": ["class"],
    "span": ["class"],
}

ALLOWED_PROTOCOLS = {"http", "https", "mailto", "tel"}

ALLOWED_TLDS = sorted(  # Sorting this list makes sure that shorter substring TLDs don't win against longer TLDs, e.g. matching '.com' before '.co'
    {suffix.rsplit(".")[-1] for suffix in PublicSuffixList()._publicsuffix},
    reverse=True,
)
TLD_REGEX = bleach.linkifier.build_url_re(
    tlds=ALLOWED_TLDS, protocols=ALLOWED_PROTOCOLS
)
EMAIL_REGEX = bleach.linkifier.build_email_re(tlds=ALLOWED_TLDS)


def link_callback(attrs, is_new, **kwargs):
    """Makes sure external links open safely."""
    safelink = kwargs.get("safelink", True)
    url = attrs.get((None, "href"), "/")
    if (
        url.startswith("mailto:")
        or url.startswith("tel:")
        # Exclude internal links
        or url_has_allowed_host_and_scheme(url, allowed_hosts=None)
    ):
        return attrs
    attrs[None, "target"] = "_blank"
    attrs[None, "rel"] = "noopener"
    if safelink:
        attrs[None, "href"] = sl(url)
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
            url_re=TLD_REGEX,
            parse_email=True,
            email_re=EMAIL_REGEX,
            skip_tags={"pre", "code"},
            callbacks=bleach.linkifier.DEFAULT_CALLBACKS + [safelink_callback],
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
            url_re=TLD_REGEX,
            parse_email=True,
            email_re=EMAIL_REGEX,
            skip_tags={"pre", "code"},
            callbacks=bleach.linkifier.DEFAULT_CALLBACKS + [abslink_callback],
        )
    ],
)
NO_LINKS_CLEANER = bleach.Cleaner(
    tags=copy(ALLOWED_TAGS)
    - {
        "a",
    },
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    strip=True,
)


STRIKETHROUGH_RE = "(~{2})(.+?)(~{2})"


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
    ],
)


def render_markdown(text: str, cleaner=CLEANER) -> str:
    """Process markdown and cleans HTML in a text input."""
    if not text:
        return ""
    body_md = cleaner.clean(md.reset().convert(str(text)))
    return mark_safe(body_md)


def render_markdown_abslinks(text: str) -> str:
    """Process markdown and cleans HTML in a text input, but use absolute links instead
    of safelink redirects."""
    return render_markdown(text, cleaner=ABSLINK_CLEANER)


@register.filter
def rich_text(text: str):
    return render_markdown(text, cleaner=CLEANER)


@register.filter
def rich_text_without_links(text: str):
    """Process markdown and cleans HTML in a text input, but without links."""
    return render_markdown(text, cleaner=NO_LINKS_CLEANER)
