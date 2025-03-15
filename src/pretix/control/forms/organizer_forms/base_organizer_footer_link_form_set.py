from django import forms
from i18nfield.forms import I18nFormSetMixin


class BaseOrganizerFooterLink(I18nFormSetMixin, forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer', None)
        if organizer:
            kwargs['locales'] = organizer.settings.get('locales')
        super().__init__(*args, **kwargs)
