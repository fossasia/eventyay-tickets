from django import forms

from pretix.base.models.devices import Gate


class GateForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        kwargs.pop("organizer")
        super().__init__(*args, **kwargs)

    class Meta:
        model = Gate
        fields = ["name", "identifier"]
