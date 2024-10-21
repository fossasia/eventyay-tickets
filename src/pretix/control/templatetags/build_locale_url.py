import urllib.parse

from django import template

register = template.Library()


@register.filter
def build_locale_url(request, locale_code):
    """
    Constructs the locale change URL by appending the locale and next path
    with the existing query string in a safe and automatic manner.
    """
    params = {'locale': locale_code, 'next': request.path}
    if request.META.get('QUERY_STRING'):
        existing_params = urllib.parse.parse_qs(request.META['QUERY_STRING'])
        params.update(existing_params)
    query_string = urllib.parse.urlencode(params, doseq=True)
    return f"{request.path}?{query_string}"
