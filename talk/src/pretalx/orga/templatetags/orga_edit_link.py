from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

register = template.Library()


@register.simple_tag()
def orga_edit_link(url, target=None):
    if target:
        url = f"{url}#{target}"
    result = f'<a href="{url}" class="btn btn-xs btn-outline-info orga-edit-link ml-auto" title="{_("Edit")}"><i class="fa fa-pencil"></i></a>'
    return mark_safe(result)
