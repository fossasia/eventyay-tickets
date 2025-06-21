from django import template
from django.utils.safestring import mark_safe

from pretalx.common.text.phrases import phrases

register = template.Library()


@register.simple_tag
def phrase(phrase_name, **kwargs):
    """Return a phrase. Used in templates when format kwargs are needed."""

    _, module, name = phrase_name.split(".")

    text = getattr(getattr(phrases, module), name)
    if not kwargs:
        return text
    # Due to being previously used in templates, most phrases are formatted
    # with old % formatting.
    return mark_safe(str(text) % kwargs)
