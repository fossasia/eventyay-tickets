from django import template

register = template.Library()


@register.filter
def build_locale_url(request, locale_code):
    """
    Constructs the locale change URL by appending the safely encoded locale
    and next path with the existing query string in a safe and automatic manner.
    """
    params = request.GET.copy()
    params.setdefault('next', request.path)
    params['locale'] = locale_code

    return f'{request.path}?{params.urlencode()}'
