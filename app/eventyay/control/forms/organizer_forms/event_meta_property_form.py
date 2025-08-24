from django import forms

from eventyay.base.models.event import EventMetaProperty


class EventMetaPropertyForm(forms.ModelForm):
    class Meta:
        model = EventMetaProperty
        fields = ['name', 'default', 'required', 'protected', 'allowed_values']
        widgets = {'default': forms.TextInput()}
