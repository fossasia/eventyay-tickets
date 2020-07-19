from functools import partial

import bleach
import markdown
from django import template
from django.utils.safestring import mark_safe
from publicsuffixlist import PublicSuffixList

register = template.Library()

ALLOWED_TAGS = [
    "a",
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
]

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

ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]

ALLOWED_TLDS = sorted(  # Sorting this list makes sure that shorter substring TLDs don't win against longer TLDs, e.g. matching '.com' before '.co'
    list(set(suffix.rsplit(".")[-1] for suffix in PublicSuffixList()._publicsuffix)),
    reverse=True,
)
TLD_REGEX = bleach.linkifier.build_url_re(tlds=ALLOWED_TLDS, protocols=ALLOWED_PROTOCOLS)
CLEANER = bleach.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    filters=[
        partial(
            bleach.linkifier.LinkifyFilter,
            url_re=TLD_REGEX,
            parse_email=True,
            skip_tags=["pre", "code"],
            callbacks=bleach.linkifier.DEFAULT_CALLBACKS,
        )
    ],
)

md = markdown.Markdown(
    extensions=[
        "markdown.extensions.nl2br",
        "markdown.extensions.sane_lists",
        "markdown.extensions.tables",
    ],
)


@register.filter
def rich_text(text: str):
    """Process markdown and cleans HTML in a text input."""
    if not text:
        return ""
    body_md = CLEANER.clean(md.reset().convert(str(text)))
    return mark_safe(body_md)
