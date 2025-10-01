from django.forms.renderers import TemplatesSetting


class TabularFormRenderer(TemplatesSetting):
    form_template_name = 'common/forms/form.html'
    field_template_name = 'common/forms/tabular_field.html'
    form_group_class = 'row'
    label_class = 'col-md-3 col-form-label'

    def render(self, template_name, context, request=None):
        context['form_group_class'] = self.form_group_class
        context['label_class'] = self.label_class
        return super().render(template_name, context, request)


class InlineFormRenderer(TabularFormRenderer):
    field_template_name = 'common/forms/field.html'
    render_label = False
    form_group_class = 'form-group-inline'
    label_class = 'sr-only'


class InlineFormLabelRenderer(InlineFormRenderer):
    render_label = True
    label_class = 'inline-form-label'
