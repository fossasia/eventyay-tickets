from pathlib import Path

from django.core.files import File
from django.forms import ClearableFileInput, PasswordInput, Textarea, Select, SelectMultiple
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
            <p class="text-muted password_strength_info hidden">
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
        return mark_safe(super().render(name, value, self.attrs) + markup)


class PasswordConfirmationInput(PasswordInput):
    def __init__(self, confirm_with=None, attrs=None, render_value=False):
        super().__init__(attrs, render_value)
        self.confirm_with = confirm_with

    def render(self, name, value, attrs=None, renderer=None):
        self.attrs["data-confirm-with"] = str(self.confirm_with)

        markup = """
        <div class="hidden password_strength_info">
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

    def get_context(self, name, value, attrs):
        attrs["accept"] = "image/*"
        return super().get_context(name, value, attrs)


class MarkdownWidget(Textarea):
    template_name = "common/widgets/markdown.html"


class EnhancedSelectMixin(Select):
    # Just add the "class: select2" attribute to the select widget
    # This is really annoying to do on the fly, because we can only override
    # widget attrs, not add them, otherwise.

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["attrs"] = add_class(ctx["widget"]["attrs"], "select2")
        if self.is_required:
            ctx["widget"]["attrs"]["required"] = ""
        return ctx

class EnhancedSelect(EnhancedSelectMixin, Select):
    pass


class EnhancedSelectMultiple(EnhancedSelectMixin, SelectMultiple):
    pass

class SelectMultipleWithCount(EnhancedSelectMultiple):
    """A widget for multi-selects that correspond to countable values.

    This widget doesn't support some of the options of the default
    SelectMultiple, most notably it doesn't support optgroups. In
    return, it takes a third value per choice, makes zero-values
    disabled and sorts options by numerical value.
    """

    def optgroups(self, name, value, attrs=None):
        choices = sorted(self.choices, key=lambda choice: choice[1].count, reverse=True)
        result = []
        for index, (option_value, label) in enumerate(choices):
            selected = str(option_value) in value
            result.append(
                self.create_option(
                    name,
                    value=option_value,
                    label=label,
                    selected=selected,
                    index=index,
                )
            )
        return [(None, result, 0)]

    def create_option(self, name, value, label, *args, count=0, **kwargs):
        option = super().create_option(name, value, str(label), *args, **kwargs)
        if label.count == 0:
            option["attrs"]["class"] = "hidden"
        return option
