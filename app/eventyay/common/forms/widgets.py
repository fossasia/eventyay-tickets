import datetime as dt
import json
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.forms import (
    ClearableFileInput,
    DateInput,
    DateTimeInput,
    PasswordInput,
    Select,
    SelectMultiple,
    Textarea,
    TextInput,
    TimeInput,
    Widget,
)
from django.utils.datastructures import MultiValueDict
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nTextarea
from i18nfield.strings import LazyI18nString


def add_class(attrs, css_class):
    attrs = attrs or {}
    class_str = (attrs.get('class', '') or '').strip()
    class_str += ' ' + css_class
    attrs['class'] = class_str.strip()
    return attrs


class PasswordStrengthInput(PasswordInput):
    def render(self, name, value, attrs=None, renderer=None):
        markup = """
        <div class="password-progress">
            <div class="password-progress-bar progress">
                <div class="progress-bar bg-warning password_strength_bar"
                     role="progressbar"
                     aria-valuenow="0"
                     aria-valuemin="0"
                     aria-valuemax="4">
                </div>
            </div>
            <p class="text-muted password_strength_info d-none">
                <span style="margin-left:5px;">
                    {message}
                </span>
            </p>
        </div>
        """.format(message=_('This password would take <em class="password_strength_time"></em> to crack.'))

        self.attrs = add_class(self.attrs, 'password_strength')
        self.attrs['autocomplete'] = 'new-password'
        return mark_safe(super().render(name, value, self.attrs) + markup)


class PasswordConfirmationInput(PasswordInput):
    def __init__(self, confirm_with=None, attrs=None, render_value=False):
        super().__init__(attrs, render_value)
        self.confirm_with = confirm_with

    def render(self, name, value, attrs=None, renderer=None):
        self.attrs['data-confirm-with'] = str(self.confirm_with)

        markup = """
        <div class="d-none password_strength_info">
            <p class="text-muted">
                <span class="label label-danger">{warning}</span>
                <span>{content}</span>
            </p>
        </div>
        """.format(warning=_('Warning'), content=_('Your passwords don’t match.'))

        self.attrs = add_class(self.attrs, 'password_confirmation')
        return mark_safe(super().render(name, value, self.attrs) + markup)


class ClearableBasenameFileInput(ClearableFileInput):
    class FakeFile(File):
        def __init__(self, file):
            self.file = file

        @property
        def name(self):
            return self.file.name

        def __str__(self):
            return Path(self.name).stem

        @property
        def url(self):
            return self.file.url

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx['widget']['value'] = self.FakeFile(value)
        return ctx


class ImageInput(ClearableBasenameFileInput):
    template_name = 'common/widgets/image_input.html'

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        widget_attrs = ctx['widget'].get('attrs') or {}
        alt = widget_attrs.pop('alt', None) or (self.attrs or {}).get('alt') or _('Image preview')
        ctx['widget']['alt_text'] = alt
        return ctx


class RichTextWidget(Textarea):
    """Tiptap-enhanced textarea for simple rich text editing.

    Renders a plain ``<textarea>`` wrapped in a ``[data-tiptap-wrapper]``
    container.  The ``tiptapLoader.js`` loader on the page detects the
    ``data-tiptap-profile`` attribute and progressively enhances the field
    with a Tiptap editor (bold, italic, underline, lists, link).

    Falls back gracefully to a plain textarea when JavaScript is disabled
    or the bundle has not loaded yet.
    """

    template_name = 'common/widgets/richtext.html'

    def __init__(self, attrs=None):
        attrs = attrs.copy() if attrs is not None else {}
        attrs.setdefault('data-tiptap-profile', 'richtext')
        super().__init__(attrs=attrs)


class MarkdownWidget(RichTextWidget):
    """Backward-compatible alias for RichTextWidget.

    Previously rendered a plain textarea with a ``data-markdown-wrapper``
    attribute.  All call sites have been migrated to ``RichTextWidget``
    directly; this alias remains so that any third-party plugin that
    still imports ``MarkdownWidget`` continues to work without change.
    """


class I18nRichTextWidget(I18nTextarea):
    """Tiptap rich text editor for i18n fields (e.g. system pages, global settings).

    Wraps each locale textarea in a ``[data-tiptap-wrapper]`` container so the
    shared editor bundle can mount one rich text editor per language.
    """

    def __init__(self, locales, field, attrs=None, **kwargs):
        attrs = attrs.copy() if attrs is not None else {}
        attrs.setdefault('data-tiptap-profile', 'richtext')
        super().__init__(locales=locales, field=field, attrs=attrs)

    def render(self, name: str, value, attrs=None, renderer=None) -> str:
        if self.is_localized:
            for widget in self.widgets:
                widget.is_localized = self.is_localized

        original_value = value
        if not isinstance(value, list):
            value = self.decompress(value)
        output = []
        final_attrs = self.build_attrs(attrs or dict())
        id_ = final_attrs.get('id', None)
        for i, widget in enumerate(self.widgets):
            if self.locales[i] not in self.enabled_locales:
                continue
            locale_code = self.locales[i]
            try:
                widget_value = value[i]
            except IndexError:
                widget_value = None

            if not widget_value and isinstance(original_value, LazyI18nString) and isinstance(original_value.data, dict):
                firstpart = locale_code.split('-')[0]
                if not widget_value:
                    similar = [
                        loc for loc in self.locales
                        if (loc.startswith(firstpart + "-") or firstpart == loc) and loc != locale_code
                    ]
                    for s in similar:
                        if original_value.data.get(s) and s not in self.enabled_locales:
                            widget_value = original_value.data.get(s)
                            break

            final_attrs_widget = final_attrs.copy()
            if id_:
                human_locale_name = dict(settings.LANGUAGES).get(locale_code, locale_code)
                final_attrs_widget['id'] = '%s_%s' % (id_, i)
                final_attrs_widget['title'] = human_locale_name
                final_attrs_widget.setdefault('placeholder', human_locale_name)

            rendered = widget.render(name + '_%s' % i, widget_value, final_attrs_widget, renderer=renderer)
            wrapped = (
                f'<div class="i18n-textarea-wrapper" data-lang="{escape(locale_code)}">'
                f'<div class="tiptap-wrapper" data-tiptap-wrapper="true">{rendered}</div>'
                f'</div>'
            )
            output.append(wrapped)

        return mark_safe(
            '<div class="i18n-form-group%s" id="%s">%s</div>' % (
                ' i18n-form-single-language' if len(output) <= 1 else '',
                escape(id_) if id_ else '',
                ''.join(output),
            )
        )


# Backward-compatible alias used by older tests and imports.
I18nRichTextEditorWidget = I18nRichTextWidget


class I18nEmailEditorWidget(I18nTextarea):
    """Tiptap email editor for i18n message fields in the Message center.

    Wraps each locale textarea in a ``[data-tiptap-wrapper]`` container so the
    shared editor bundle can mount one editor per language tab.
    """

    def __init__(self, locales, field, attrs=None, placeholders=None, preview_url=''):
        attrs = attrs.copy() if attrs is not None else {}
        attrs.setdefault('data-tiptap-profile', 'email')
        if placeholders:
            attrs['data-tiptap-placeholders'] = json.dumps(list(placeholders))
        if preview_url:
            attrs['data-tiptap-preview-url'] = preview_url
        super().__init__(locales=locales, field=field, attrs=attrs)

    def format_output(self, rendered_widgets, id_):
        wrapped = [
            (
                f'<div class="tiptap-wrapper" data-tiptap-wrapper="true" '
                f'data-email-editor="true">{widget}</div>'
            )
            for widget in rendered_widgets
        ]
        return super().format_output(wrapped, id_)


class EmailEditorWidget(Textarea):
    """Tiptap-enhanced textarea for email body editing.

    Extends the richtext profile with a placeholder variable insertion
    menu and an optional preview button.  Available placeholder variable
    names are passed via ``data-tiptap-placeholders`` as a JSON array so
    the JS bundle can render the insertion dropdown without a server round-trip.

    Args:
        placeholders: Sequence of placeholder variable names to expose in
            the insertion menu, e.g. ``['attendee_name', 'event_name']``.
        preview_url: Optional URL for the email preview AJAX endpoint.
    """

    template_name = 'common/widgets/email_editor.html'

    def __init__(self, attrs=None, placeholders=None, preview_url=''):
        attrs = attrs.copy() if attrs is not None else {}
        attrs.setdefault('data-tiptap-profile', 'email')
        if placeholders:
            attrs['data-tiptap-placeholders'] = json.dumps(list(placeholders))
        if preview_url:
            attrs['data-tiptap-preview-url'] = preview_url
        super().__init__(attrs=attrs)
        self.placeholders = list(placeholders) if placeholders else []
        self.preview_url = preview_url


class EnhancedSelectMixin(Select):
    # - add the "class: enhanced" attribute to the select widget
    # - if `description_field` is set, set data-description on options
    # - if `color_field` is set, set data-color on options
    def __init__(self, attrs=None, choices=(), description_field=None, color_field=None):
        self.description_field = description_field
        self.color_field = color_field
        super().__init__(attrs, choices)

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx['widget']['attrs'] = add_class(ctx['widget']['attrs'], 'enhanced')
        ctx['widget']['attrs']['tabindex'] = '-1'
        return ctx

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value and getattr(value, 'instance', None):
            if self.description_field and (description := getattr(value.instance, self.description_field, None)):
                option['attrs']['data-description'] = description
            if self.color_field and (color := getattr(value.instance, self.color_field, None)):
                option['attrs']['data-color'] = color
        else:
            if self.color_field and callable(self.color_field):
                option['attrs']['data-color'] = self.color_field(value)
        return option


class EnhancedSelect(EnhancedSelectMixin, Select):
    pass


class EnhancedSelectMultiple(EnhancedSelectMixin, SelectMultiple):
    pass


def get_count(value, label):
    count = None
    instance = getattr(value, 'instance', None)
    if instance:
        count = getattr(instance, 'count', 0)
    count = count or getattr(label, 'count', 0)
    if callable(count):
        return count(label)
    return count


class SelectMultipleWithCount(EnhancedSelectMultiple):
    """A widget for multi-selects that correspond to countable values.

    This widget doesn't support some of the options of the default
    SelectMultiple, most notably it doesn't support optgroups. In
    return, it takes a third value per choice, makes zero-values
    disabled and sorts options by numerical value.
    """

    def optgroups(self, name, value, attrs=None):
        choices = sorted(self.choices, key=lambda choice: get_count(*choice), reverse=True)
        result = []
        for index, (option_value, label) in enumerate(choices):
            count = get_count(option_value, label)
            if count == 0:
                continue
            selected = str(option_value) in value
            result.append(
                self.create_option(
                    name,
                    value=option_value,
                    label=label,
                    selected=selected,
                    index=index,
                    count=count,
                )
            )
        return [(None, result, 0)]

    def create_option(self, name, value, label, *args, count=0, **kwargs):
        label = f'{label} ({count})'
        return super().create_option(name, value, label, *args, **kwargs)


class SearchInput(TextInput):
    input_type = 'search'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['attrs']['placeholder'] = _('Search')
        return context


class TextInputWithAddon(TextInput):
    template_name = 'common/widgets/text_input_with_addon.html'

    def __init__(self, attrs=None, addon_before=None, addon_after=None):
        super().__init__(attrs)
        self.addon_before = addon_before
        self.addon_after = addon_after

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['addon_before'] = self.addon_before
        context['widget']['addon_after'] = self.addon_after
        return context


class SlidesWidget(Widget):
    template_name = 'common/widgets/slides_input.html'

    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.max_items = None
        self.max_size = None

    @staticmethod
    def files_field_name(name):
        return f'{name}_files'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        
        clear_ids = []
        if isinstance(value, dict):
            clear_ids = value.get('clear_ids', [])

        existing_resources = getattr(self, 'existing_resources', [])
        current_resources = [
            resource for resource in existing_resources
            if str(resource.pk) not in clear_ids
        ]

        context['widget']['current_resources'] = current_resources
        context['widget']['existing_value'] = bool(current_resources)
        context['widget']['max_items'] = self.max_items
        context['widget']['max_size'] = self.max_size
        context['widget']['current_count'] = len(current_resources)
        context['widget']['remaining_items'] = (
            max(self.max_items - len(current_resources), 0) if self.max_items else None
        )
        context['widget']['files_name'] = self.files_field_name(name)
        context['widget']['files_id'] = f'id_{self.files_field_name(name)}'
        context['widget']['clear_name'] = self.clear_checkbox_name(name)
        context['widget']['is_re_render'] = isinstance(value, dict)
        return context

    @staticmethod
    def clear_checkbox_name(name):
        return f'{name}_clear_ids'

    def value_from_datadict(self, data, files, name):
        stored_value = data.get(name)
        if isinstance(stored_value, dict):
            clear_ids = stored_value.get('clear_ids', [])
        else:
            if isinstance(data, MultiValueDict):
                clear_ids = data.getlist(self.clear_checkbox_name(name))
            else:
                clear_ids = data.get(self.clear_checkbox_name(name), [])
        return {
            'resources': files.getlist(self.files_field_name(name)),
            'clear_ids': clear_ids,
        }


class HtmlDateInput(DateInput):
    input_type = 'date'

    def format_value(self, value):
        if value and isinstance(value, (dt.date, dt.datetime)):
            return value.strftime('%Y-%m-%d')
        return value


class HtmlDateTimeInput(DateTimeInput):
    input_type = 'datetime-local'

    def format_value(self, value):
        if value and isinstance(value, dt.datetime):
            return value.strftime('%Y-%m-%dT%H:%M')
        return value


class HtmlTimeInput(TimeInput):
    input_type = 'time'

    def format_value(self, value):
        if value and isinstance(value, (dt.time, dt.datetime)):
            return value.strftime('%H:%M')
        return value
