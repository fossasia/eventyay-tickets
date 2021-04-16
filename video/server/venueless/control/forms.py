from django import forms
from django.contrib.auth import get_user_model

from venueless.core.models import World
from venueless.core.models.world import FEATURE_FLAGS

User = get_user_model()


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
