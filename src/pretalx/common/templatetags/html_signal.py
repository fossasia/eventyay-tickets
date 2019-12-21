import importlib

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def html_signal(signame: str, **kwargs):
    """Send a signal and return the concatenated return values of all
    responses.

    Usage::

        {% html_signal event "path.to.signal" argument="value" ... %}
    """
    sigstr = signame.rsplit(".", 1)
    sigmod = importlib.import_module(sigstr[0])
    signal = getattr(sigmod, sigstr[1])
    _html = []
    for receiver, response in signal.send(**kwargs):
        if response:
            _html.append(response)
    return mark_safe("".join(_html))
