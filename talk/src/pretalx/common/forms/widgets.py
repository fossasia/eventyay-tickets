import datetime as dt
from pathlib import Path

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
)
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _


def add_class(attrs, css_class):
    attrs = attrs or {}
    class_str = (attrs.get("class", "") or "").strip()
    class_str += " " + css_class
    attrs["class"] = class_str.strip()
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
        """.format(
            message=_(
                'This password would take <em class="password_strength_time"></em> to crack.'
            )
        )

        self.attrs = add_class(self.attrs, "password_strength")
        self.attrs["autocomplete"] = "new-password"
        return mark_safe(super().render(name, value, self.attrs) + markup)


class PasswordConfirmationInput(PasswordInput):
    def __init__(self, confirm_with=None, attrs=None, render_value=False):
        super().__init__(attrs, render_value)
        self.confirm_with = confirm_with

    def render(self, name, value, attrs=None, renderer=None):
        self.attrs["data-confirm-with"] = str(self.confirm_with)

        markup = """
        <div class="d-none password_strength_info">
            <p class="text-muted">
                <span class="label label-danger">{warning}</span>
                <span>{content}</span>
            </p>
        </div>
        """.format(
            warning=_("Warning"), content=_("Your passwords don’t match.")
        )

        self.attrs = add_class(self.attrs, "password_confirmation")
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
        ctx["widget"]["value"] = self.FakeFile(value)
        return ctx


class ImageInput(ClearableBasenameFileInput):
    template_name = "common/widgets/image_input.html"


class MarkdownWidget(Textarea):
    template_name = "common/widgets/markdown.html"


class EnhancedSelectMixin(Select):
    # - add the "class: enhanced" attribute to the select widget
    # - if `description_field` is set, set data-description on options
    # - if `color_field` is set, set data-color on options
    def __init__(
        self, attrs=None, choices=(), description_field=None, color_field=None
    ):
        self.description_field = description_field
        self.color_field = color_field
        super().__init__(attrs, choices)

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["attrs"] = add_class(ctx["widget"]["attrs"], "enhanced")
        ctx["widget"]["attrs"]["tabindex"] = "-1"
        return ctx

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value and getattr(value, "instance", None):
            if self.description_field and (
                description := getattr(value.instance, self.description_field, None)
            ):
                option["attrs"]["data-description"] = description
            if self.color_field and (
                color := getattr(value.instance, self.color_field, None)
            ):
                option["attrs"]["data-color"] = color
        else:
            if self.color_field and callable(self.color_field):
                option["attrs"]["data-color"] = self.color_field(value)
        return option


class EnhancedSelect(EnhancedSelectMixin, Select):
    pass


class EnhancedSelectMultiple(EnhancedSelectMixin, SelectMultiple):
    pass


def get_count(value, label):
    count = None
    instance = getattr(value, "instance", None)
    if instance:
        count = getattr(instance, "count", 0)
    count = count or getattr(label, "count", 0)
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
        choices = sorted(
            self.choices, key=lambda choice: get_count(*choice), reverse=True
        )
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
        label = f"{label} ({count})"
        return super().create_option(name, value, label, *args, **kwargs)


class SearchInput(TextInput):
    input_type = "search"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["attrs"]["placeholder"] = _("Search")
        return context


class TextInputWithAddon(TextInput):
    template_name = "common/widgets/text_input_with_addon.html"

    def __init__(self, attrs=None, addon_before=None, addon_after=None):
        super().__init__(attrs)
        self.addon_before = addon_before
        self.addon_after = addon_after

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["addon_before"] = self.addon_before
        context["widget"]["addon_after"] = self.addon_after
        return context


class HtmlDateInput(DateInput):
    input_type = "date"

    def format_value(self, value):
        if value and isinstance(value, (dt.date, dt.datetime)):
            return value.strftime("%Y-%m-%d")
        return value


class HtmlDateTimeInput(DateTimeInput):
    input_type = "datetime-local"

    def format_value(self, value):
        if value and isinstance(value, dt.datetime):
            return value.strftime("%Y-%m-%dT%H:%M")
        return value


class HtmlTimeInput(TimeInput):
    input_type = "time"

    def format_value(self, value):
        if value and isinstance(value, (dt.time, dt.datetime)):
            return value.strftime("%H:%M")
        return value
