import i18nfield.forms
from django import forms
from django.utils.translation import ugettext as _


class SearchForm(forms.Form):
    q = forms.CharField(label=_('Search'), required=False)


class I18nFormSet(i18nfield.forms.I18nModelFormSet):
    # compatibility shim for django-i18nfield library

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        if event:
            kwargs['locales'] = event.locales
        super().__init__(*args, **kwargs)
