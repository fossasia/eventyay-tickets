from django import forms

from pretix.base.models.event import EventMetaProperty


class EventMetaPropertyForm(forms.ModelForm):
    class Meta:
        model = EventMetaProperty
        fields = ['name', 'default', 'required', 'protected', 'allowed_values']
        widgets = {
            'default': forms.TextInput()
        }
