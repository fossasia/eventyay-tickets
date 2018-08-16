from django import template
from django.utils.translation import ugettext_lazy as _

register = template.Library()


@register.filter
def times(text: str):
    """Add a tag that really really really could be a standard tag."""
    if text is None:
        return ""
    str_text = str(text)
    if str_text == '1':
        return _('once')
    if str_text == '2':
        return _('twice')
    return _('{number} times').format(number=str_text)
