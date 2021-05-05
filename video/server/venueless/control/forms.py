from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from venueless.core.models import BBBServer, JanusServer, TurnServer, World
from venueless.core.models.world import FEATURE_FLAGS, PlannedUsage

User = get_user_model()
SECRET_REDACTED = "*****"


class SecretKeyWidget(forms.TextInput):
    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        attrs.update(
            {
                "autocomplete": "new-password"  # see https://bugs.chromium.org/p/chromium/issues/detail?id=370363#c7
            }
        )
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        if value:
            value = value[:3] + SECRET_REDACTED
        return super().get_context(name, value, attrs)


class SecretKeyField(forms.CharField):
    widget = SecretKeyWidget

    def has_changed(self, initial, data):
        if data.endswith(SECRET_REDACTED):
            return False
        return super().has_changed(initial, data)

    def run_validators(self, value):
        if value.endswith(SECRET_REDACTED):
            return
        return super().run_validators(value)


class HasSecretsMixin:
    def save(self):
        for k, v in self.cleaned_data.items():
            if isinstance(self.fields.get(k), SecretKeyField) and self.cleaned_data.get(
                k
            ).endswith(SECRET_REDACTED):
                self.cleaned_data[k] = self.initial[k]
                setattr(self.instance, k, self.initial[k])
        return super().save()


class PasswordMixin:
    def clean(self):
        super().clean()
        if self.cleaned_data.get("password") != self.cleaned_data.get(
            "repeat_password"
        ):
            raise forms.ValidationError("Passwords do not match!")


class SignupForm(PasswordMixin, forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    repeat_password = forms.CharField(widget=forms.PasswordInput())

    def save(self):
        user = User.objects.create(
            email=self.cleaned_data.get("email"),
            username=self.cleaned_data.get("username"),
            is_staff=True,
        )
        user.set_password(self.cleaned_data.get("password"))
        user.save()
        return user

    class Meta:
        model = User
        fields = ("email", "username", "password")


class ProfileForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    new_password = forms.CharField(widget=forms.PasswordInput(), required=False)

    def clean_password(self):
        data = self.cleaned_data["password"]
        if not self.instance.check_password(data):
            raise forms.ValidationError("Wrong password!")
        return data

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        if self.cleaned_data.get("new_password"):
            instance.set_password(self.cleaned_data["new_password"])
            instance.save()
        return instance

    class Meta:
        model = User
        fields = ("email", "username", "password")


class WorldForm(forms.ModelForm):
    feature_flags = forms.MultipleChoiceField(
        choices=[(a, a) for a in FEATURE_FLAGS],
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = World
        fields = (
            "id",
            "title",
            "domain",
            "locale",
            "timezone",
            "feature_flags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["id"].disabled = True


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "is_staff",
            "is_active",
            "is_superuser",
        )


class DateInput(forms.DateInput):
    input_type = "date"


class PlannedUsageForm(forms.ModelForm):
    class Meta:
        model = PlannedUsage
        fields = ("start", "end", "attendees", "notes")
        widgets = {
            "notes": forms.Textarea(attrs={"rows": "1", "placeholder": "Notes"}),
            "attendees": forms.NumberInput(
                attrs={"placeholder": "Number of attendees"}
            ),
            "start": DateInput(attrs={"placeholder": "Start date"}, format="%Y-%m-%d"),
            "end": DateInput(attrs={"placeholder": "End date"}, format="%Y-%m-%d"),
        }


PlannedUsageFormSet = inlineformset_factory(
    World, PlannedUsage, PlannedUsageForm, can_delete=True, extra=0
)


class BBBServerForm(HasSecretsMixin, forms.ModelForm):
    class Meta:
        model = BBBServer
        fields = (
            "url",
            "active",
            "world_exclusive",
            "rooms_only",
            "secret",
        )
        field_classes = {"secret": SecretKeyField}


class JanusServerForm(HasSecretsMixin, forms.ModelForm):
    class Meta:
        model = JanusServer
        fields = (
            "url",
            "active",
            "room_create_key",
            "world_exclusive",
        )
        field_classes = {"room_create_key": SecretKeyField}


class TurnServerForm(HasSecretsMixin, forms.ModelForm):
    class Meta:
        model = TurnServer
        fields = (
            "active",
            "hostname",
            "auth_secret",
            "world_exclusive",
        )
        field_classes = {"auth_secret": SecretKeyField}
