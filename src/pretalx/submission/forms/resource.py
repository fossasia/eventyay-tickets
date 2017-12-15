from django import forms

from pretalx.submission.models import Resource


class ResourceForm(forms.ModelForm):

    class Meta:
        model = Resource
        fields = [
            'resource', 'description',
        ]
