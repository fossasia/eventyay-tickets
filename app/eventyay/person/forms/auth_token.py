from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.common.forms.widgets import (
    EnhancedSelect,
    EnhancedSelectMultiple,
    HtmlDateTimeInput,
)
from eventyay.base.models.auth_token import (
    ENDPOINTS,
    PERMISSION_CHOICES,
    READ_PERMISSIONS,
    WRITE_PERMISSIONS,
    UserApiToken,
)


class AuthTokenForm(forms.ModelForm):
    permission_preset = forms.ChoiceField(
        label=_("Permissions"),
        required=False,
        choices=(
            ("read", _("Read all endpoints")),
            ("write", _("Read and write all endpoints")),
            ("custom", _("Customize permissions and endpoints")),
        ),
        help_text=_("Choose a preset or configure detailed permissions below."),
        widget=EnhancedSelect,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["events"].queryset = user.get_events_with_any_permission()

        self.endpoint_fields = {}
        for endpoint in ENDPOINTS:
            self.fields[f"endpoint_{endpoint}"] = forms.MultipleChoiceField(
                label=f"/{endpoint}",
                required=False,
                choices=PERMISSION_CHOICES,
                widget=forms.CheckboxSelectMultiple,
                initial=READ_PERMISSIONS,
            )
            self.endpoint_fields[f"endpoint_{endpoint}"] = self.fields[
                f"endpoint_{endpoint}"
            ]

    def get_endpoint_fields(self):
        """Used in templates, so has to return the actual fields."""
        return [
            (field_name, self[field_name]) for field_name in self.endpoint_fields.keys()
        ]

    def save(self, *args, **kwargs):
        self.instance.user = self.user
        self.instance.endpoints = self.cleaned_data["endpoints"]
        return super().save(*args, **kwargs)

    class Meta:
        model = UserApiToken
        fields = ["name", "events", "expires", "permission_preset"]
        widgets = {
            "expires": HtmlDateTimeInput,
            "events": EnhancedSelectMultiple,
        }

    def clean(self):
        data = super().clean()
        if data.get("permission_preset") == "read":
            data["endpoints"] = {endpoint: READ_PERMISSIONS for endpoint in ENDPOINTS}
        elif data.get("permission_preset") == "write":
            data["endpoints"] = {endpoint: WRITE_PERMISSIONS for endpoint in ENDPOINTS}
        else:
            data["endpoints"] = {}
            for field_name in self.endpoint_fields.keys():
                permissions = self.cleaned_data.get(field_name)
                endpoint = field_name.replace("endpoint_", "")
                invalid_perms = set(permissions) - set(WRITE_PERMISSIONS)
                if invalid_perms:
                    self.add_error(
                        field_name,
                        _("Invalid permissions selected: {perms}").format(
                            perms=", ".join(invalid_perms)
                        ),
                    )
                data["endpoints"][endpoint] = list(permissions)
        return data
