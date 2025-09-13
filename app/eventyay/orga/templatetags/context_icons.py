from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def get_top_menu_item_icon_class(context):
    request = context['request']
    return 'fa-group' if getattr(request, 'organiser', None) else 'fa-tachometer'
