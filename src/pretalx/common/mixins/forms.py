import re
from functools import partial

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

    def clean_variable_field(self, min_length, max_length, count_in, key):
        value = self.cleaned_data.get(key)
        if count_in == 'chars':
            length = len(value)
        else:
            length = len(re.findall(r'\b\w+\b', value))
        if (min_length and min_length > length) or (max_length and max_length < length):
            error_message = get_help_text('', min_length, max_length, count_in)
            errors = {
                'chars': _('You wrote {count} characters.'),
                'words': _('You wrote {count} words.'),
            }
            error_message += ' ' + str(errors[count_in]).format(count=length)
            raise forms.ValidationError(error_message)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        count_chars = self.event.settings.cfp_count_length_in == 'chars'
        for key in self.Meta.request_require:
            request = self.event.settings.get(f'cfp_request_{key}')
            require = self.event.settings.get(f'cfp_require_{key}')
            if not request:
                self.fields.pop(key)
            else:
                self.fields[key].required = require
                min_value = self.event.settings.get(f'cfp_{key}_min_length')
                max_value = self.event.settings.get(f'cfp_{key}_max_length')
                if min_value or max_value:
                    if min_value and count_chars:
                        self.fields[key].widget.attrs[f'minlength'] = min_value
                    if max_value and count_chars:
                        self.fields[key].widget.attrs[f'maxlength'] = max_value
                    setattr(self, f'clean_{key}', partial(self.clean_variable_field, key=key, min_length=min_value, max_length=max_value, count_in=self.event.settings.cfp_count_length_in))
                    self.fields[key].help_text = get_help_text(
                        self.fields[key].help_text, min_value, max_value, self.event.settings.cfp_count_length_in,
                    )
