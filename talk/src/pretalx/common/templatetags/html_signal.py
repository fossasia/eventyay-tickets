from django import template
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def html_signal(signal_name: str, **kwargs):
    """Send a signal and return the concatenated return values of all
    responses.

    Usage::

        {% html_signal event "path.to.signal" argument="value" ... %}
    """
    signal = import_string(signal_name)
    _html = []
    for _receiver, response in signal.send(**kwargs):
        if response:
            _html.append(response)
    return mark_safe("".join(_html))
