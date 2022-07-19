from django import forms
from django.utils.translation import gettext_lazy as _

from .models import VenuelessSettings


class VenuelessSettingsForm(forms.ModelForm):

    token = forms.CharField(
        help_text=_(
            "Generate a token with the trait 'world:api' in the Config -> Token Generator menu in Venueless. Leave empty to leave unchanged."
        ),
        label=_("Venueless Token"),
        required=True,
    )
    url = forms.URLField(
        help_text=_("URL of your Venueless event"),
        label=_("Venueless URL"),
        required=True,
    )
    return_url = forms.CharField(widget=forms.HiddenInput())

    def __init__(
        self,
        *args,
        event=None,
        initial_token=None,
        initial_url=None,
        return_url=None,
        **kwargs
    ):
        self.instance, _ = VenuelessSettings.objects.get_or_create(event=event)
        super().__init__(*args, **kwargs, instance=self.instance)
        if not event:
            raise Exception("Missing event")

        if initial_token:
            self.fields["token"].initial = initial_token
            self.initial["token"] = initial_token
        if initial_url:
            self.fields["url"].initial = initial_url
            self.initial["url"] = initial_url
        if return_url:
            self.fields["return_url"].initial = return_url
            self.initial["return_url"] = return_url

    class Meta:
        model = VenuelessSettings
        fields = ("token", "url", "return_url")
