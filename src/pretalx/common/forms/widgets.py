from pathlib import Path

from django.core.files import File
from django.forms import ClearableFileInput, PasswordInput, Textarea
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _


class PasswordStrengthInput(PasswordInput):
    def render(self, name, value, attrs=None, renderer=None):
        markup = """
        <div class="password-progress">
            <div class="password-progress-bar progress">
                <div class="progress-bar progress-bar-warning password_strength_bar"
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

        self.attrs["class"] = " ".join(
            self.attrs.get("class", "").split(" ") + ["password_strength"]
        )
        return mark_safe(super().render(name, value, self.attrs) + markup)

    class Media:  # Note: we don't use {{ form.media }}, since it doesn't allow us to load media async, and the zxcvbn scripts are horribly slow
        js = ("vendored/zxcvbn.js", "common/js/password_strength.js")


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
            warning=_("Warning"), content=_("Your passwords don't match.")
        )

        self.attrs["class"] = " ".join(
            self.attrs.get("class", "").split(" ") + ["password_confirmation"]
        )

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
    def get_context(self, name, value, attrs):
        attrs["accept"] = "image/*"
        return super().get_context(name, value, attrs)


class MarkdownWidget(Textarea):
    template_name = "common/widgets/markdown.html"
