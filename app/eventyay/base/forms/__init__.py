import logging
import os

import i18nfield.forms
from django import forms
from django.conf import settings
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from django.core.validators import URLValidator
from django.forms.models import ModelFormMetaclass
from django.utils.crypto import get_random_string
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from formtools.wizard.views import SessionWizardView
from hierarkey.forms import HierarkeyForm
from i18nfield.strings import LazyI18nString

from eventyay.base.reldate import RelativeDateField, RelativeDateTimeField
from eventyay.common.urls import is_http_url
from eventyay.helpers.image_optimize import optimize_uploaded_image
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
        from eventyay.base.settings import DEFAULTS

        self.obj = kwargs.get('obj', None)
        self.locales = self.obj.settings.get('locales') if self.obj else kwargs.pop('locales', None)
        kwargs['attribute_name'] = 'settings'
        kwargs['locales'] = self.locales
        kwargs['initial'] = self.get_initial_settings()
        original_freeze = None

        def freeze_with_safe_initial():
            return kwargs['initial'].copy()

        if self.obj:
            original_freeze = self.obj.settings.freeze
            object.__setattr__(self.obj.settings, 'freeze', freeze_with_safe_initial)
        try:
            super().__init__(*args, **kwargs)
        finally:
            if self.obj and original_freeze:
                object.__setattr__(self.obj.settings, 'freeze', original_freeze)
        for fname in self.auto_fields:
            kwargs = DEFAULTS[fname].get('form_kwargs', {})
            if callable(kwargs):
                kwargs = kwargs()
            kwargs.setdefault('required', False)
            form_class = DEFAULTS[fname]['form_class']
            field = form_class(**kwargs)
            if isinstance(field, i18nfield.forms.I18nFormField):
                field.widget.enabled_locales = self.locales
            if fname == 'primary_font':
                from eventyay.base.models import Event  # noqa: PLC0415
                if isinstance(self.obj, Event):
                    inherited_font = None
                    if hasattr(self.obj, 'organizer'):
                        inherited_font = self.obj.organizer.settings.get('primary_font')
                    if not inherited_font:
                        inherited_font = 'Open Sans'
                    field.choices = [('', _('Default (Inherit: {})').format(inherited_font))] + list(field.choices)
                    if 'primary_font' not in self.obj.settings._cache():
                        self.initial['primary_font'] = ''
                    field.widget.obj = self.obj
            self.fields[fname] = field
            if fname not in self.initial or self.initial[fname] is None:
                default_value = DEFAULTS[fname].get('default')
                if default_value:
                    self.initial[fname] = default_value
        for k, f in self.fields.items():
            if isinstance(f, (RelativeDateTimeField, RelativeDateField)):
                f.set_event(self.obj)

    def get_initial_settings(self):
        if not self.obj:
            return {}

        return self.build_initial_settings(self.obj.settings)

    def build_initial_settings(self, settings_proxy):
        initial = {}
        if settings_proxy._parent:
            initial.update(
                self.build_initial_settings(getattr(settings_proxy._parent, settings_proxy._h.attribute_name))
            )

        for key, default in settings_proxy._h.defaults.items():
            initial[key] = self.get_initial_setting_value(settings_proxy, key, default.type, default.value)

        for key in settings_proxy._cache():
            declared_type = settings_proxy._h.get_declared_type(key)
            initial[key] = self.get_initial_setting_value(settings_proxy, key, declared_type)

        return initial

    def get_initial_setting_value(self, settings_proxy, key, declared_type, default=None):
        if declared_type is File:
            value = settings_proxy.get(key, as_type=str, default=default)
            if isinstance(value, str) and is_http_url(value):
                return value
        return settings_proxy.get(key, as_type=declared_type, default=default)

    def clean(self):
        cleaned_data = super().clean()
        
        for k, v in list(cleaned_data.items()):
            if isinstance(v, UploadedFile) and k in {
                'invoice_logo_image', 'startpage_header_image',
            }:
                try:
                    opt = optimize_uploaded_image(v, k)
                    orig_name = os.path.splitext(v.name or 'upload')[0]
                    new_name = f'{orig_name}.{opt.optimized_ext}'
                    cleaned_data[k] = SimpleUploadedFile(
                        name=new_name,
                        content=opt.optimized.read(),
                        content_type=getattr(v, 'content_type', None)
                    )
                except (ValueError, OSError) as e:
                    self.add_error(k, str(e))
                    if hasattr(v, 'seek'):
                        v.seek(0)
        return cleaned_data

    def save(self):
        for k, v in self.cleaned_data.items():
            if isinstance(self.fields.get(k), SecretKeySettingsField) and self.cleaned_data.get(k) == SECRET_REDACTED:
                self.cleaned_data[k] = self.initial[k]

        if self.cleaned_data.get('primary_font') == '':
            self.cleaned_data['primary_font'] = None

        return super().save()

    def get_new_filename(self, name: str) -> str:
        from eventyay.base.models import Event  # noqa: PLC0415

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
                'autocomplete': 'new-password',  # see https://bugs.chromium.org/p/chromium/issues/detail?id=370363#c7
                'type': 'password',
                'class': (attrs.get('class', '') + ' secret-key-input').strip(),
            }
        )
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        if value:
            value = SECRET_REDACTED
        context = super().get_context(name, value, attrs)
        return context

    def render(self, name, value, attrs=None, renderer=None):
        output = super().render(name, value, attrs, renderer)
        show_label = str(_('Show secret key'))
        hide_label = str(_('Hide secret key'))
        toggle_html = (
            '<div class="secret-key-wrapper">'
            f'{output}'
            '<button type="button" class="secret-toggle" '
            f'aria-label="{show_label}" '
            f'data-label-show="{show_label}" '
            f'data-label-hide="{hide_label}" '
            'aria-pressed="false">'
            '<i class="fa fa-eye"></i>'
            '</button>'
            '</div>'
        )
        return mark_safe(toggle_html)


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
    def __init__(self, attrs=None, **kwargs):
        attrs = attrs.copy() if attrs is not None else {}
        attrs.setdefault('data-markdown-field', 'true')
        super().__init__(attrs=attrs, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        if not isinstance(value, dict):
            value = self.decompress(value)

        output = []
        id_ = attrs.get('id') if attrs else None
        lang_dict = dict(settings.LANGUAGES)
        for i, widget in enumerate(self.widgets):
            locale_code = self.locales[i]
            human_locale_name = str(lang_dict.get(locale_code, locale_code))
            widget_value = value.get(locale_code, '') if isinstance(value, dict) else ''

            final_attrs_widget = (attrs or {}).copy()
            if id_:
                final_attrs_widget['id'] = f'{id_}_{i}'
                final_attrs_widget['title'] = human_locale_name
                final_attrs_widget.setdefault('placeholder', human_locale_name)

            textarea_html = widget.render(f'{name}_{i}', widget_value, final_attrs_widget, renderer=renderer)

            wrapped_html = f'''
            <div class="i18n-textarea-wrapper" data-lang="{escape(locale_code)}">
                {textarea_html}
            </div>
            '''
            output.append(wrapped_html)

        return mark_safe(f'<div class="i18n-form-group" id="{escape(id_) if id_ else ""}">{  "".join(output) }</div>')


class I18nAutoExpandingTextarea(i18nfield.forms.I18nTextarea):
    def __init__(self, attrs=None, **kwargs):
        default_attrs = {
            'class': 'form-control auto-expanding-textarea',
            'data-auto-expand': 'true',
            'style': 'min-height: 320px; max-height: 400px; overflow-y: auto; resize: vertical; transition: height 0.2s ease-in-out; box-sizing: border-box;',
        }
        if attrs:
            if 'class' in attrs:
                default_attrs['class'] = default_attrs['class'] + ' ' + attrs['class']
            if 'style' in attrs:
                default_attrs['style'] = default_attrs['style'] + '; ' + attrs['style']
            attrs_copy = attrs.copy()
            attrs_copy.pop('class', None)
            attrs_copy.pop('style', None)
            default_attrs.update(attrs_copy)
        super().__init__(attrs=default_attrs, **kwargs)

    class Media:
        js = ('eventyay-common/js/auto-expanding-textarea.js',)


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
