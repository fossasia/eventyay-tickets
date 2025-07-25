from django import forms
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from pretalx.common.forms.fields import NewPasswordConfirmationField, NewPasswordField
from pretalx.common.text.phrases import phrases
from pretalx.person.models import User

EMAIL_ADDRESS_ERROR = _("Please choose a different email address.")


class LoginInfoForm(forms.ModelForm):
    error_messages = {
        "pw_current_wrong": _("The current password you entered was not correct.")
    }

    old_password = forms.CharField(
        widget=forms.PasswordInput, label=_("Password (current)"), required=True
    )
    password = NewPasswordField(label=phrases.base.new_password, required=False)
    password_repeat = NewPasswordConfirmationField(
        label=phrases.base.password_repeat, required=False, confirm_with="password"
    )

    def clean_old_password(self):
        old_pw = self.cleaned_data.get("old_password")
        if not check_password(old_pw, self.user.password):
            raise forms.ValidationError(
                self.error_messages["pw_current_wrong"], code="pw_current_wrong"
            )
        return old_pw

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.exclude(pk=self.user.pk).filter(email__iexact=email):
            raise ValidationError(EMAIL_ADDRESS_ERROR)
        return email

    def clean(self):
        data = super().clean()
        password = self.cleaned_data.get("password")
        if password and password != self.cleaned_data.get("password_repeat"):
            self.add_error(
                "password_repeat", ValidationError(phrases.base.passwords_differ)
            )
        return data

    def __init__(self, user, *args, **kwargs):
        self.user = user
        kwargs["instance"] = user
        super().__init__(*args, **kwargs)

    def save(self):
        super().save()
        password = self.cleaned_data.get("password")
        if password:
            self.user.change_password(password)

    class Meta:
        model = User
        fields = ("email",)
