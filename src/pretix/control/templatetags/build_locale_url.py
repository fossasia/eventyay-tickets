import urllib.parse
from django import template

register = template.Library()


@register.filter
def build_locale_url(request, locale_code):
    """
    Constructs the locale change URL by appending the locale and
    next path and query string to the URL.
    """
    # Build base URL with locale
    base_url = f"{request.path}?locale={locale_code}"

    # Append query string if it exists
    if request.META.get('QUERY_STRING'):
        query_string = urllib.parse.urlencode(urllib.parse.parse_qsl(request.META['QUERY_STRING']))
        return f"{base_url}%3F{query_string}"

    return base_url
