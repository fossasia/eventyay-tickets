from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from django_scopes import scopes_disabled

from eventyay.base.models import (
    BBBServer,
    JanusServer,
    JitsiServer,
    LoungeMeshServer,
    Organizer,
    Room,
    TurnServer,
)
from eventyay.base.models.event import (
    Event,
    FEATURE_FLAGS,
    EventPlannedUsage as PlannedUsage,
    default_feature_flags,
)
from eventyay.base.services.jitsi import normalize_server_url

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
        for k in self.cleaned_data.keys():
            if (
                isinstance(self.fields.get(k), SecretKeyField)
                and self.cleaned_data.get(k).endswith(SECRET_REDACTED)
                and k in self.initial
            ):
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

            is_staff=True,
        )
        user.set_password(self.cleaned_data.get("password"))
        user.save()
        return user

    class Meta:
        model = User
        fields = ("email", "password")


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
        fields = ("email", "password")


class EventForm(forms.ModelForm):
    feature_flags = forms.MultipleChoiceField(
        choices=[(a, a) for a in FEATURE_FLAGS],
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Event
        fields = (
            "id",
            "domain",
            "locale",
            "timezone",
            "feature_flags",
            "external_auth_url",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and "id" in self.fields:
            self.fields["id"].disabled = True
        feature_flags = self.instance.feature_flags if self.instance else {}
        if isinstance(feature_flags, dict):
            selected = [
                feature for feature in FEATURE_FLAGS if feature_flags.get(feature)
            ]
        elif isinstance(feature_flags, list):
            selected = [
                feature for feature in FEATURE_FLAGS if feature in feature_flags
            ]
        else:
            selected = []
        self.initial["feature_flags"] = selected

    def clean_id(self):
        d = self.cleaned_data["id"]
        if not self.instance or not self.instance.pk:
            if Event.objects.filter(id__iexact=d).exists():
                raise ValidationError("ID is already in use")
        return d

    def clean_feature_flags(self):
        selected = set(self.cleaned_data["feature_flags"])
        current = self.instance.feature_flags if self.instance else {}
        if isinstance(current, dict):
            flags = dict(current)
        else:
            flags = default_feature_flags()
        for feature in FEATURE_FLAGS:
            if feature in selected:
                flags[feature] = True
            else:
                flags.pop(feature, None)
        return flags


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
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
    Event, PlannedUsage, PlannedUsageForm, can_delete=True, extra=0
)


class VideoServerScopeMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "organizers" in self.fields:
            self.fields["organizers"].queryset = Organizer.objects.all().order_by("name")
            self.fields["organizers"].required = False
            self.fields["organizers"].widget.attrs.update({
                "class": "form-control select2-multi",
                "data-placeholder": _("Search and select organizers..."),
                "multiple": "multiple",
            })
            self.fields["organizers"].label = _("Organizers")
            self.fields["organizers"].help_text = _(
                "Optional: Restrict usage of this server to all events under selected organizers."
            )

        if "events" in self.fields:
            with scopes_disabled():
                self.fields["events"].queryset = Event.objects.all().order_by("name")
            self.fields["events"].required = False
            self.fields["events"].widget.attrs.update({
                "class": "form-control select2-multi",
                "data-placeholder": _("Search and select events..."),
                "multiple": "multiple",
            })
            self.fields["events"].label = _("Events")
            self.fields["events"].help_text = _(
                "Optional: Restrict usage of this server to specific events."
            )

        if "event_exclusive" in self.fields:
            with scopes_disabled():
                self.fields["event_exclusive"].queryset = Event.objects.all().order_by("name")
            self.fields["event_exclusive"].required = False
            self.fields["event_exclusive"].label = _("Legacy Exclusive Event")
            self.fields["event_exclusive"].help_text = _(
                "Optional legacy single-event constraint. Use 'Events' above for multiple events."
            )


class BBBServerForm(VideoServerScopeMixin, HasSecretsMixin, forms.ModelForm):
    class Meta:
        model = BBBServer
        fields = (
            "url",
            "active",
            "organizers",
            "events",
            "event_exclusive",
            "secret",
        )
        field_classes = {"secret": SecretKeyField}


class JanusServerForm(VideoServerScopeMixin, HasSecretsMixin, forms.ModelForm):
    class Meta:
        model = JanusServer
        fields = (
            "url",
            "active",
            "room_create_key",
            "organizers",
            "events",
            "event_exclusive",
        )
        field_classes = {"room_create_key": SecretKeyField}


class JitsiServerForm(VideoServerScopeMixin, HasSecretsMixin, forms.ModelForm):
    def clean_url(self):
        normalized = normalize_server_url(self.cleaned_data["url"])
        if not normalized or normalized["protocol"] != "https:":
            raise ValidationError(_("Enter a valid Jitsi server URL."))
        return normalized["url"]

    class Meta:
        model = JitsiServer
        fields = (
            "url",
            "active",
            "app_id",
            "key_id",
            "app_secret",
            "organizers",
            "events",
            "event_exclusive",
        )
        field_classes = {"app_secret": SecretKeyField}


class TurnServerForm(VideoServerScopeMixin, HasSecretsMixin, forms.ModelForm):
    class Meta:
        model = TurnServer
        fields = (
            "active",
            "hostname",
            "auth_secret",
            "organizers",
            "events",
            "event_exclusive",
        )
        field_classes = {"auth_secret": SecretKeyField}


class LoungeMeshServerForm(VideoServerScopeMixin, HasSecretsMixin, forms.ModelForm):
    class Meta:
        model = LoungeMeshServer
        fields = (
            "url",
            "active",
            "api_secret",
            "jitsi_app_id",
            "jitsi_app_secret",
            "organizers",
            "events",
            "event_exclusive",
        )
        field_classes = {
            "api_secret": SecretKeyField,
            "jitsi_app_secret": SecretKeyField,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["api_secret"].required = True
        self.fields["jitsi_app_id"].required = True
        self.fields["jitsi_app_secret"].required = True
        if not self.instance.pk and not self.initial.get("api_secret"):
            import secrets

            self.initial["api_secret"] = f"lms_sec_{secrets.token_urlsafe(24)}"

    def clean_url(self):
        url = self.cleaned_data.get("url")
        if url:
            url = url.strip().rstrip("/")
        return url



class BBBMoveRoomForm(forms.Form):
    room = forms.ModelChoiceField(
        label=_('Room ID'), queryset=Room.objects.all(), widget=forms.TextInput
    )
    server = forms.ModelChoiceField(
        label=_('Target Server'),
        queryset=BBBServer.objects.filter(active=True).order_by("url"),
    )
