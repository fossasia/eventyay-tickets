from django import template

register = template.Library()


@register.filter(name='getproduct')
def getproduct_filter(value, productname):
    if not value:
        return ''

    return value[productname]
