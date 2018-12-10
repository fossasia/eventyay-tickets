from django import forms
from django.utils.translation import ugettext_lazy as _

from pretalx.common.forms.utils import get_help_text


class ReadOnlyFlag:
    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_only = read_only
        if read_only:
            for field in self.fields.values():
                field.disabled = True

    def clean(self):
        if self.read_only:
            raise forms.ValidationError(_('You are trying to change read only data.'))
        return super().clean()


class RequestRequire:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in self.Meta.request_require:
            request = self.event.settings.get(f'cfp_request_{key}')
            require = self.event.settings.get(f'cfp_require_{key}')
            if not request:
                self.fields.pop(key)
            else:
                self.fields[key].required = require
                min_value = self.event.settings.get(f'cfp_{key}_min_length')
                max_value = self.event.settings.get(f'cfp_{key}_max_length')
                if min_value:
                    self.fields[key].widget.attrs[f'minlength'] = min_value
                if max_value:
                    self.fields[key].widget.attrs[f'maxlength'] = max_value
                self.fields[key].help_text = get_help_text(
                    self.fields[key].help_text, min_value, max_value
                )
