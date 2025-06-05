import logging

import i18nfield.forms
from django import forms
from django.core.validators import URLValidator
from django.forms.models import ModelFormMetaclass
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from formtools.wizard.views import SessionWizardView
from hierarkey.forms import HierarkeyForm
from i18nfield.strings import LazyI18nString

from pretix.base.reldate import RelativeDateField, RelativeDateTimeField

from .validators import PlaceholderValidator  # NOQA

logger = logging.getLogger(__name__)


class BaseI18nModelForm(i18nfield.forms.BaseI18nModelForm):
    # compatibility shim for django-i18nfield library

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        if self.event:
            kwargs['locales'] = self.event.settings.get('locales')
        super().__init__(*args, **kwargs)


class I18nModelForm(BaseI18nModelForm, metaclass=ModelFormMetaclass):
    pass


class I18nFormSet(i18nfield.forms.I18nModelFormSet):
    # compatibility shim for django-i18nfield library

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        if self.event:
            kwargs['locales'] = self.event.settings.get('locales')
        super().__init__(*args, **kwargs)


class I18nInlineFormSet(i18nfield.forms.I18nInlineFormSet):
    # compatibility shim for django-i18nfield library

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        if event:
            kwargs['locales'] = event.settings.get('locales')
        super().__init__(*args, **kwargs)


SECRET_REDACTED = '*****'


class SettingsForm(i18nfield.forms.I18nFormMixin, HierarkeyForm):
    auto_fields = []

    def __init__(self, *args, **kwargs):
        from pretix.base.settings import DEFAULTS

        self.obj = kwargs.get('obj', None)
        self.locales = self.obj.settings.get('locales') if self.obj else kwargs.pop('locales', None)
        kwargs['attribute_name'] = 'settings'
        kwargs['locales'] = self.locales
        kwargs['initial'] = self.obj.settings.freeze()
        super().__init__(*args, **kwargs)
        for fname in self.auto_fields:
            kwargs = DEFAULTS[fname].get('form_kwargs', {})
            if callable(kwargs):
                kwargs = kwargs()
            kwargs.setdefault('required', False)
            field = DEFAULTS[fname]['form_class'](**kwargs)
            if isinstance(field, i18nfield.forms.I18nFormField):
                field.widget.enabled_locales = self.locales
            self.fields[fname] = field
        for k, f in self.fields.items():
            if isinstance(f, (RelativeDateTimeField, RelativeDateField)):
                f.set_event(self.obj)

    def save(self):
        for k, v in self.cleaned_data.items():
            if isinstance(self.fields.get(k), SecretKeySettingsField) and self.cleaned_data.get(k) == SECRET_REDACTED:
                self.cleaned_data[k] = self.initial[k]
        return super().save()

    def get_new_filename(self, name: str) -> str:
        from pretix.base.models import Event

        nonce = get_random_string(length=8)
        if isinstance(self.obj, Event):
            fname = '%s/%s/%s.%s.%s' % (
                self.obj.organizer.slug,
                self.obj.slug,
                name,
                nonce,
                name.split('.')[-1],
            )
        else:
            fname = '%s/%s.%s.%s' % (self.obj.slug, name, nonce, name.split('.')[-1])
        # TODO: make sure pub is always correct
        return 'pub/' + fname


class PrefixForm(forms.Form):
    prefix = forms.CharField(widget=forms.HiddenInput)


class SafeSessionWizardView(SessionWizardView):
    def get_prefix(self, request, *args, **kwargs):
        if hasattr(request, '_session_wizard_prefix'):
            return request._session_wizard_prefix
        prefix_form = PrefixForm(self.request.POST, prefix=super().get_prefix(request, *args, **kwargs))
        if not prefix_form.is_valid():
            request._session_wizard_prefix = get_random_string(length=24)
        else:
            request._session_wizard_prefix = prefix_form.cleaned_data['prefix']
        return request._session_wizard_prefix

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        context['wizard']['prefix_form'] = PrefixForm(
            prefix=super().get_prefix(self.request),
            initial={'prefix': self.get_prefix(self.request)},
        )
        return context


class SecretKeySettingsWidget(forms.TextInput):
    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        attrs.update(
            {
                'autocomplete': 'new-password'  # see https://bugs.chromium.org/p/chromium/issues/detail?id=370363#c7
            }
        )
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        if value:
            value = SECRET_REDACTED
        return super().get_context(name, value, attrs)


class SecretKeySettingsField(forms.CharField):
    widget = SecretKeySettingsWidget

    def has_changed(self, initial, data):
        if data == SECRET_REDACTED:
            return False
        return super().has_changed(initial, data)

    def run_validators(self, value):
        if value == SECRET_REDACTED:
            return
        return super().run_validators(value)


class I18nMarkdownTextarea(i18nfield.forms.I18nTextarea):
    def format_output(self, rendered_widgets) -> str:
        markdown_note = _('You can use {name} in this field.').format(
            name='<a href="https://en.wikipedia.org/wiki/Markdown" target="_blank">Markdown</a>'
        )
        rendered_widgets.append(f'<div class="i18n-field-markdown-note">{markdown_note}</div>')
        return super().format_output(rendered_widgets)


class I18nURLFormField(i18nfield.forms.I18nFormField):
    """
    Custom form field to handle internationalized URL inputs. It extends the I18nFormField
    and ensures that all provided URLs are valid.

    Methods:
        clean(value: LazyI18nString) -> LazyI18nString:
            Validates the URL(s) in the provided internationalized input.
    """

    def clean(self, value) -> LazyI18nString:
        """
        Cleans and validates the internationalized URL input.

        Args:
            value (LazyI18nString): The input value to clean and validate.

        Returns:
            LazyI18nString: The cleaned and validated input value.

        Raises:
            ValidationError: If any of the URLs are invalid.
        """
        value = super().clean(value)
        if not value:
            return value

        url_validator = URLValidator()

        if isinstance(value.data, dict):
            for val in value.data.values():
                if val:
                    url_validator(val)
        else:
            url_validator(value.data)

        return value
