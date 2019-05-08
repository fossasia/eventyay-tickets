import django.utils.safestring
from django import template
from django.utils.translation import ugettext_lazy as _

register = template.Library()


@register.filter
def copyable(value):
    value = str(value)
    if '"' in value:
        return value
    title = str(_("Copy"))
    return django.utils.safestring.mark_safe(f"""
    <span data-destination="{value}"
            class="copyable-text"
            data-toggle="tooltip"
            data-placement="top"
            title="{title}"
    >
        {value}
    </span>""")
