from django import forms

from pretalx.submission.models import Resource


class ResourceForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = True
        self.fields['description'].widget.attrs['required'] = True

    class Meta:
        model = Resource
        fields = ['resource', 'description']
