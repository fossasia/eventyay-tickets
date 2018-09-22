from bootstrap4.renderers import FieldRenderer
from bootstrap4.text import text_value
from django.forms import CheckboxInput
from django.forms.utils import escape, flatatt
from django.utils.html import format_html, strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import pgettext
from i18nfield.forms import I18nFormField


def render_label(
    content, label_for=None, label_class=None, label_title='', optional=False
):
    """Render a label with content."""
    attrs = {}
    if label_for:
        attrs['for'] = label_for
    if label_class:
        attrs['class'] = label_class
    if label_title:
        attrs['title'] = label_title
    builder = '<{tag}{attrs}>{content}{opt}</{tag}>'
    return format_html(
        builder,
        tag='label',
        attrs=mark_safe(flatatt(attrs)) if attrs else '',
        opt=mark_safe(
            '<br><span class="optional">{}</span>'.format(pgettext('form', 'Optional'))
        )
        if optional
        else '',
        content=text_value(content),
    )


class EventInlineFieldRenderer(FieldRenderer):
    LAYOUT = 'inline'

    def __init__(self, *args, **kwargs):
        self.use_label = kwargs.pop('use_label', True)
        kwargs['layout'] = (
            self.LAYOUT if kwargs['layout'].startswith('event') else kwargs['layout']
        )
        super().__init__(*args, **kwargs)

    def put_inside_label(self, html):
        """Do not put inputs inside labels."""
        label = render_label(
            content=mark_safe(self.field.label if self.use_label else ''),
            label_for=self.field.id_for_label,
            label_title=escape(strip_tags(self.field_help)),
        )
        return mark_safe(html + label)


class EventFieldRenderer(EventInlineFieldRenderer):
    LAYOUT = 'horizontal'

    def add_label(self, html):
        label = self.get_label()

        if isinstance(self.field.field, I18nFormField):
            required = self.field.field.one_required
        else:
            required = getattr(self.field.field, '_required', self.field.field.required)

        html = (
            render_label(
                label,
                label_for=self.field.id_for_label,
                label_class=self.get_label_class(),
                optional=not required and not isinstance(self.widget, CheckboxInput),
            )
            + html
        )
        return html
