import i18nfield.forms
from django import forms
from django.utils.translation import gettext as _


class SearchForm(forms.Form):
    q = forms.CharField(label=_("Search"), required=False)


class I18nFormSet(i18nfield.forms.I18nModelFormSet):
    """Compatibility shim for django-i18nfield."""

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        kwargs["locales"] = getattr(event, "locales", [])
        super().__init__(*args, **kwargs)


class I18nEventFormSet(i18nfield.forms.I18nModelFormSet):
    """Compatibility shim for django-i18nfield."""

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        kwargs["locales"] = getattr(self.event, "locales", [])
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs["locales"] = self.locales
        kwargs["event"] = self.event
        return super()._construct_form(i, **kwargs)
