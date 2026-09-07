import html
import re
import urllib.parse
from copy import copy
from functools import partial

# TODO: Remove bleach import
import bleach
import markdown
# TODO: Remove bleach import
from bleach import DEFAULT_CALLBACKS
# TODO: Remove bleach import
from bleach.linkifier import build_email_re, build_url_re
from django import template
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from markdownify import markdownify as html_to_markdown

try:
    from publicsuffixlist import PublicSuffixList

    TLD_SET = sorted({suffix.rsplit('.')[-1] for suffix in PublicSuffixList()._publicsuffix}, reverse=True)
except ImportError:
    from tlds import tld_set

    TLD_SET = sorted(tld_set, key=len, reverse=True)

from i18nfield.strings import LazyI18nString

from eventyay.common.views.redirect import safelink as sl

register = template.Library()

ALLOWED_TAGS = {
    'a',
    'abbr',
    'acronym',
    'b',
    'blockquote',
    'br',
    'code',
    'del',
    'div',
    'em',
    'hr',
    'i',
    'li',
    'ol',
    'strong',
    'u',
    'ul',
    'p',
    'pre',
    'span',
    'table',
    'tbody',
    'thead',
    'tr',
    'td',
    'th',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
}

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'class'],
    'abbr': ['title'],
    'acronym': ['title'],
    'table': ['width'],
    'td': ['width', 'align'],
    'div': ['class'],
    'p': ['class'],
    'span': ['class', 'title'],
}

ALLOWED_PROTOCOLS = {'http', 'https', 'mailto', 'tel'}

# TODO: Remove bleach library
URL_RE = build_url_re(tlds=TLD_SET)
EMAIL_RE = build_email_re(tlds=TLD_SET)


def link_callback(attrs, is_new, safelink=True):
    url = attrs.get((None, 'href'), '/')
    if url.startswith('mailto:') or url.startswith('tel:') or url_has_allowed_host_and_scheme(url, allowed_hosts=None):
        return attrs
    attrs[None, 'target'] = '_blank'
    attrs[None, 'rel'] = 'noopener'
    if safelink:
        url = html.unescape(url)
        attrs[None, 'href'] = sl(url)
    else:
        url = html.unescape(url)
        attrs[None, 'href'] = urllib.parse.urljoin(settings.SITE_URL, url)
    return attrs


safelink_callback = partial(link_callback, safelink=True)
abslink_callback = partial(link_callback, safelink=False)

# TODO: Implement nh3 equivalent
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
            skip_tags={'pre', 'code'},
            callbacks=DEFAULT_CALLBACKS + [safelink_callback],
        )
    ],
)

# TODO: Implement nh3 equivalent
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
            skip_tags={'pre', 'code'},
            callbacks=DEFAULT_CALLBACKS + [abslink_callback],
        )
    ],
)

# TODO: Implement nh3 equivalent
NO_LINKS_CLEANER = bleach.Cleaner(
    tags=copy(ALLOWED_TAGS) - {'a'},
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    strip=True,
)

STRIKETHROUGH_RE = '(~{2})(.+?)(~{2})'

# Email bodies may include trusted placeholder HTML such as QR ``<img>`` tags
# (data-URI PNGs) and CTA buttons. Keep these allowlists scoped to email
# compilation so public rich-text rendering stays stricter.
EMAIL_ALLOWED_TAGS = ALLOWED_TAGS | {'img'}
EMAIL_ALLOWED_ATTRIBUTES = {
    **ALLOWED_ATTRIBUTES,
    'img': ['src', 'alt', 'width', 'height'],
}
# ``data`` is allowed only so QR ``<img src="data:image/...">`` survives. Anchor
# ``href`` values that use ``data:`` are rejected in ``email_allowed_attributes``.
EMAIL_ALLOWED_PROTOCOLS = ALLOWED_PROTOCOLS | {'data'}

_TIPTAP_BLOCK_START_RE = re.compile(
    r'^\s*<(p|ul|ol|blockquote)(\s|>)',
    re.IGNORECASE | re.DOTALL,
)


def _is_tiptap_email_html(source: str) -> bool:
    """Return True when *source* looks like HTML from the Tiptap email editor.

    ``nh3.is_html()`` is too broad: legacy Markdown bodies may contain inline
    tags such as ``<br>`` or ``<b>`` and must still be compiled.  Tiptap
    output is always block-structured (``<p>``, lists, blockquote) or contains
    placeholder chips with ``data-variable``.
    """
    if not source:
        return False
    source = str(source)
    if 'data-variable=' in source:
        return True
    return bool(_TIPTAP_BLOCK_START_RE.match(source))


_PREVIEW_PLACEHOLDER_CONTEXT: tuple[str, ...] = (
    'event',
    'order',
    'position',
    'position_or_address',
    'team',
    'invoice_address',
)


def expand_email_preview_placeholders(html_body: str, event, *, locale: str | None = None) -> str:
    """Replace ``{placeholder}`` tokens / Tiptap chips with sample values for editor preview."""
    from eventyay.base.i18n import language
    from eventyay.base.services.mail import expand_email_variable_chips

    resolved_locale = locale or event.settings.locale
    if resolved_locale not in event.settings.locales:
        resolved_locale = event.settings.locale

    with language(resolved_locale, event.settings.region):
        context_dict = build_email_preview_context(event, list(_PREVIEW_PLACEHOLDER_CONTEXT))
        expanded = html_body.format_map(context_dict)
        return expand_email_variable_chips(expanded, dict(context_dict))


def compile_email_body(source: str) -> str:
    """Render an email body fragment as HTML.

    Plain-text and legacy Markdown bodies are compiled with
    ``markdown_compile_email``.  Content that is already HTML (for example from
    the Tiptap email editor) is sanitized and returned.
    """
    if not source:
        return source
    source = str(source)
    if _is_tiptap_email_html(source):
        from eventyay.common.sanitizers import sanitize_email_html
        return sanitize_email_html(source)
    return markdown_compile_email(source)


def email_allowed_attributes(tag: str, name: str, value: str) -> bool:
    """Allowlist email HTML attributes; forbid ``data:`` links on anchors."""
    allowed_for_tag = EMAIL_ALLOWED_ATTRIBUTES.get(tag)
    if not allowed_for_tag or name not in allowed_for_tag:
        return False
    if tag == 'a' and name == 'href' and value.lstrip().lower().startswith('data:'):
        return False
    if tag == 'img' and name == 'src':
        normalized = value.lstrip().lower()
        return normalized.startswith(('data:image/', 'http://', 'https://', '/'))
    return True


def is_placeholder_html_sample(sample: str) -> bool:
    """Return True when a placeholder sample is trusted HTML (button, QR image)."""
    stripped = str(sample).lstrip()
    return stripped.startswith('<') and not stripped.startswith('</')


def build_email_preview_context(event, base_parameters: list[str]):
    """Build sendmail preview context, keeping HTML placeholder samples intact."""
    from django.utils.translation import gettext

    from eventyay.base.email import get_available_placeholders as get_base_placeholders
    from eventyay.mail.context import get_available_placeholders as get_talk_placeholders
    from eventyay.base.services.mail import TolerantDict

    context_dict = TolerantDict()
    title = html.escape(str(gettext('This value will be replaced based on dynamic parameters.')))
    
    # Get placeholders from base module
    base_placeholders = get_base_placeholders(event, list(base_parameters))
    
    # Get placeholders from talk module
    talk_placeholders = get_talk_placeholders(event, list(base_parameters))
        
    all_placeholders = {**base_placeholders, **talk_placeholders}

    for key, placeholder in all_placeholders.items():
        sample = str(placeholder.render_sample(event))
        if is_placeholder_html_sample(sample):
            context_dict[key] = sample
        else:
            context_dict[key] = f'<span class="placeholder" title="{title}">{html.escape(sample)}</span>'
    return context_dict


# TODO: Implement nh3 equivalent
def markdown_compile_email(source):
    linker = bleach.Linker(
        url_re=URL_RE,
        email_re=EMAIL_RE,
        callbacks=DEFAULT_CALLBACKS + [abslink_callback],
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
            tags=EMAIL_ALLOWED_TAGS,
            attributes=email_allowed_attributes,
            protocols=EMAIL_ALLOWED_PROTOCOLS,
        )
    )


class StrikeThroughExtension(markdown.Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            markdown.inlinepatterns.SimpleTagPattern(STRIKETHROUGH_RE, 'del'),
            'strikethrough',
            200,
        )


md = markdown.Markdown(
    extensions=[
        'markdown.extensions.nl2br',
        'markdown.extensions.sane_lists',
        'markdown.extensions.tables',
        'markdown.extensions.fenced_code',
        'markdown.extensions.codehilite',
        'markdown.extensions.md_in_html',
        StrikeThroughExtension(),
    ]
)


def compile_markdown(text: str) -> str:
    if not text:
        return ''
    return md.reset().convert(str(text))


def render_markdown(text: str, cleaner=CLEANER) -> str:
    if not text:
        return ''
    body_md = cleaner.clean(compile_markdown(text))
    return mark_safe(body_md)


def render_markdown_abslinks(text: str) -> str:
    return render_markdown(text, cleaner=ABSLINK_CLEANER)


def _unwrap_single_paragraph(html: str) -> str:
    """Return inline HTML for snippet contexts by removing one outer <p> wrapper."""
    match = re.fullmatch(r'<p>(.*)</p>\s*', html, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    return html


@register.filter
def rich_text(text: str):
    return render_markdown(text, cleaner=CLEANER)


@register.filter
def rich_text_without_links(text: str):
    return render_markdown(text, cleaner=NO_LINKS_CLEANER)


@register.filter
def rich_text_snippet(text: str):
    rendered = render_markdown(text, cleaner=ABSLINK_CLEANER)
    if not rendered:
        return rendered
    return mark_safe(_unwrap_single_paragraph(str(rendered)))


@register.filter
def html_to_markdown_filter(html_text: str) -> str:
    """Convert HTML to markdown format."""
    return html_text if not html_text else html_to_markdown(html_text)


@register.filter
def append_colon(text: LazyI18nString) -> str:
    text = str(text).strip()
    if not text:
        return ''
    return text if text[-1] in ['.', '!', '?', ':', ';'] else f'{text}:'
