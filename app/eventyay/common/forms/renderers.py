from django.forms.renderers import TemplatesSetting
from django.forms.widgets import Widget


def renders_option_list(widget: Widget) -> bool:
    """Whether a widget renders its choices as a list of radio buttons or checkboxes.

    Such widgets show their help text above the first option, so that it is read
    before the choices instead of after the last one.
    """
    input_type = getattr(widget, 'input_type', None)
    if input_type == 'radio':
        return True
    return input_type == 'checkbox' and getattr(widget, 'allow_multiple_selected', False)


class TabularFormRenderer(TemplatesSetting):
    form_template_name = 'common/forms/form.html'
    field_template_name = 'common/forms/tabular_field.html'
    form_group_class = 'row'
    label_class = 'col-md-3 col-form-label'
    help_text_above_options = True

    def render(self, template_name, context, request=None):
        context['form_group_class'] = self.form_group_class
        context['label_class'] = self.label_class
        if self.help_text_above_options and (field := context.get('field')) is not None:
            context['help_text_above'] = renders_option_list(field.field.widget)
        return super().render(template_name, context, request)


class InlineFormRenderer(TabularFormRenderer):
    field_template_name = 'common/forms/field.html'
    render_label = False
    form_group_class = 'form-group-inline'
    label_class = 'sr-only'
    help_text_above_options = False


class InlineFormLabelRenderer(InlineFormRenderer):
    render_label = True
    label_class = 'inline-form-label'
