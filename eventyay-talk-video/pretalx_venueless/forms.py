from django import forms
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm
from pretalx.common.forms.widgets import HtmlDateTimeInput

from .models import VenuelessSettings


class VenuelessSettingsForm(I18nModelForm):
    token = forms.CharField(
        help_text=_(
            "Generate a token with the trait 'world:api' in the Config -> Token Generator menu in Eventyay video. Leave empty to leave unchanged."
        ),
        label=_("Eventyay video Token"),
        required=True,
    )
    url = forms.URLField(
        help_text=_("URL of your Eventyay video event"),
        label=_("Eventyay video URL"),
        required=True,
    )
    return_url = forms.CharField(widget=forms.HiddenInput(), required=False)

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
        super().__init__(*args, **kwargs, instance=self.instance, locales=event.locales)
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

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("show_join_link"):
            # validate that all required data for join links has been provided
            required_fields = ("join_url", "secret", "issuer", "audience")
            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(
                        field,
                        _(
                            "This field is required if you want to show a join button to your speakers."
                        ),
                    )
        return cleaned_data

    class Meta:
        model = VenuelessSettings
        fields = (
            "token",
            "url",
            "show_join_link",
            "join_url",
            "secret",
            "issuer",
            "audience",
            "join_start",
            "join_text",
        )
        widgets = {
            "join_start": HtmlDateTimeInput,
            "secret": forms.TextInput(),
            "audience": forms.TextInput(),
            "issuer": forms.TextInput(),
        }
