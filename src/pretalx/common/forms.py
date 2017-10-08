import i18nfield.forms
from django import forms
from django.utils.translation import ugettext as _


class SearchForm(forms.Form):
    q = forms.CharField(label=_('Search'), required=False)


class ReadOnlyFlag:
    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        if read_only:
            for field_name, field in self.fields.items():
                field.disabled = True


class I18nFormSet(i18nfield.forms.I18nModelFormSet):
    # compatibility shim for django-i18nfield library

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        if event:
            kwargs['locales'] = event.locales
        super().__init__(*args, **kwargs)
