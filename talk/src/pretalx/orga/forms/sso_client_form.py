from allauth.socialaccount.models import SocialApp
from django import forms


class SSOClientForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["secret"].required = True

    class Meta:
        model = SocialApp
        fields = ["client_id", "secret"]
