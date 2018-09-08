from xml.sax.saxutils import escape

import django.utils.safestring
from django import template

register = template.Library()
strip_ascii = {c: None for c in list(range(0, 9)) + list(range(11, 32))}


@register.filter
def xmlescape(text):
    text = str(text)  # resolve lazy i18n string
    text = text.translate(strip_ascii)  # remove ascii control characters
    text = escape(text)  # escape ><&
    text = text.encode('ascii', 'xmlcharrefreplace').decode()  # convert all non-ascii to &#xxx;
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    return django.utils.safestring.mark_safe(text)
