import i18nfield.forms
from django.forms.models import ModelFormMetaclass
from django.utils import six


class ReadOnlyFlag:
    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        if read_only:
            for field_name, field in self.fields.items():
                field.disabled = True


class BaseI18nModelForm(i18nfield.forms.BaseI18nModelForm):
    # compatibility shim for django-i18nfield library

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        if event:
            kwargs['locales'] = event.locales
        super().__init__(*args, **kwargs)


class I18nModelForm(six.with_metaclass(ModelFormMetaclass, BaseI18nModelForm)):
    pass


class I18nFormSet(i18nfield.forms.I18nModelFormSet):
    # compatibility shim for django-i18nfield library

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        if event:
            kwargs['locales'] = event.locales
        super().__init__(*args, **kwargs)


class I18nInlineFormSet(i18nfield.forms.I18nInlineFormSet):
    # compatibility shim for django-i18nfield library

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        if event:
            kwargs['locales'] = event.locales
        super().__init__(*args, **kwargs)
