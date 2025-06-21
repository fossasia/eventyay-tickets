from django import template

register = template.Library()


@register.filter
def get_feature_flag(event, feature_flag: str):
    return event.get_feature_flag(feature_flag)
