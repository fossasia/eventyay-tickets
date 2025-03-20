from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from pretix.base.models.devices import Device
from pretix.control.forms.event import SafeEventMultipleChoiceField


class DeviceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)
        self.fields['limit_events'].queryset = organizer.events.all().order_by('-has_subevents', '-date_from')
        self.fields['gate'].queryset = organizer.gates.all()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('all_events') and not cleaned_data.get('limit_events'):
            raise ValidationError(_('Your device will not have access to anything, please select some events.'))

        return cleaned_data

    class Meta:
        model = Device
        fields = ['name', 'all_events', 'limit_events', 'security_profile', 'gate']
        widgets = {
            'limit_events': forms.CheckboxSelectMultiple(
                attrs={
                    'data-inverse-dependency': '#id_all_events',
                    'class': 'scrolling-multiple-choice scrolling-multiple-choice-large',
                }
            ),
        }
        field_classes = {'limit_events': SafeEventMultipleChoiceField}
