from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def get_top_menu_item_icon_class(context):
    request = context['request']
    if getattr(request, 'event', None):
        return 'fa-tachometer'
    elif getattr(request, 'organiser', None):
        return 'fa-group'
    return 'fa-user'
