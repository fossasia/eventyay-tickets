from django import template
from django.forms.widgets import CheckboxInput

register = template.Library()


@register.filter
def is_checkbox_input(field):
    return isinstance(field.field.widget, CheckboxInput)
