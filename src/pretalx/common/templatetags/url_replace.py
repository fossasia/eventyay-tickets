from django import template

register = template.Library()


@register.simple_tag
def url_replace(request, field, value):
    queryparams = request.GET.copy()
    queryparams[field] = value
    return queryparams.urlencode()
