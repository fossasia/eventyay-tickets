from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone, translation
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField
from i18nfield.forms import I18nModelForm

from pretalx.cfp.forms.cfp import CfPFormMixin
from pretalx.common.forms.fields import (
    ImageField,
    NewPasswordConfirmationField,
    NewPasswordField,
    SizeFileField,
)
from pretalx.common.forms.mixins import (
    I18nHelpText,
    PublicContent,
    ReadOnlyFlag,
    RequestRequire,
)
from pretalx.common.forms.renderers import InlineFormLabelRenderer, InlineFormRenderer
from pretalx.common.forms.widgets import (
    EnhancedSelect,
    EnhancedSelectMultiple,
    MarkdownWidget,
)
from pretalx.common.text.phrases import phrases
from pretalx.event.models import Event
from pretalx.person.models import SpeakerInformation, SpeakerProfile, User
from pretalx.schedule.forms import AvailabilitiesFormMixin
from pretalx.submission.models import Question
from pretalx.submission.models.submission import SubmissionStates

EMAIL_ADDRESS_ERROR = _("Please choose a different email address.")


class UserForm(CfPFormMixin, forms.Form):
    default_renderer = InlineFormLabelRenderer

    login_email = forms.EmailField(
        max_length=60,
        label=phrases.base.enter_email,
        required=False,
        widget=forms.EmailInput(attrs={"autocomplete": "username"}),
    )
    login_password = forms.CharField(
        label=_("Password"),
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    register_name = forms.CharField(
        label=_("Name"),
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    register_email = forms.EmailField(
        label=phrases.base.enter_email,
        required=False,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    register_password = NewPasswordField(
        label=_("Password"),
        required=False,
    )
    register_password_repeat = NewPasswordConfirmationField(
        label=_("Password (again)"),
        required=False,
        confirm_with="register_password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    FIELDS_ERROR = _(
        "Please fill all fields of either the login or the registration form."
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        self.fields["register_email"].widget.attrs = {
            "placeholder": phrases.base.enter_email
        }

    def _clean_login(self, data):
        try:
            uname = User.objects.get(email__iexact=data.get("login_email")).email
        except User.DoesNotExist:  # We do this to avoid timing attacks
            uname = "user@invalid"

        user = authenticate(username=uname, password=data.get("login_password"))

        if user is None:
            raise ValidationError(
                _(
                    "No user account matches the entered credentials. "
                    "Are you sure that you typed your password correctly?"
                )
            )

        if not user.is_active:
            raise ValidationError(_("Sorry, your account is currently disabled."))

        data["user_id"] = user.pk

    def _clean_register(self, data):
        if data.get("register_password") != data.get("register_password_repeat"):
            self.add_error(
                "register_password_repeat",
                ValidationError(phrases.base.passwords_differ),
            )

        if User.objects.filter(email__iexact=data.get("register_email")).exists():
            self.add_error(
                "register_email",
                ValidationError(
                    _(
                        "We already have a user with that email address. Did you already register "
                        "before and just need to log in?"
                    )
                ),
            )

    def clean(self):
        data = super().clean()

        if data.get("login_email") and data.get("login_password"):
            self._clean_login(data)
        elif (
            data.get("register_email")
            and data.get("register_password")
            and data.get("register_name")
        ):
            self._clean_register(data)
        else:
            raise ValidationError(self.FIELDS_ERROR)

        return data

    def save(self):
        data = self.cleaned_data
        if data.get("login_email") and data.get("login_password"):
            return data["user_id"]

        # We already checked that all fields are filled, but sometimes
        # they end up empty regardless. No idea why and how.
        if not (
            data.get("register_email")
            and data.get("register_password")
            and data.get("register_name")
        ):
            raise ValidationError(self.FIELDS_ERROR)

        user = User.objects.create_user(
            name=data.get("register_name").strip(),
            email=data.get("register_email").lower().strip(),
            password=data.get("register_password"),
            locale=translation.get_language(),
            timezone=timezone.get_current_timezone_name(),
        )
        data["user_id"] = user.pk
        return user.pk


class SpeakerProfileForm(
    CfPFormMixin,
    AvailabilitiesFormMixin,
    ReadOnlyFlag,
    PublicContent,
    RequestRequire,
    forms.ModelForm,
):
    USER_FIELDS = [
        "name",
        "email",
        "avatar",
        "avatar_source",
        "avatar_license",
        "get_gravatar",
    ]
    FIRST_TIME_EXCLUDE = ["email"]

    def __init__(self, *args, name=None, **kwargs):
        self.user = kwargs.pop("user", None)
        self.event = kwargs.pop("event", None)
        self.with_email = kwargs.pop("with_email", True)
        self.essential_only = kwargs.pop("essential_only", False)
        kwargs["instance"] = None
        if self.user:
            kwargs["instance"] = self.user.event_profile(self.event)
        super().__init__(*args, **kwargs, event=self.event, limit_to_rooms=True)
        read_only = kwargs.get("read_only", False)
        initial = kwargs.get("initial", {})
        initial["name"] = name

        if self.user:
            initial.update(
                {field: getattr(self.user, field) for field in self.user_fields}
            )
        for field in self.user_fields:
            field_class = self.Meta.field_classes.get(
                field, User._meta.get_field(field).formfield
            )
            self.fields[field] = field_class(
                initial=initial.get(field),
                disabled=read_only,
                help_text=User._meta.get_field(field).help_text,
            )
            if self.Meta.widgets.get(field):
                self.fields[field].widget = self.Meta.widgets.get(field)()
            self._update_cfp_texts(field)

        if not self.event.cfp.request_avatar:
            self.fields.pop("avatar", None)
            self.fields.pop("avatar_source", None)
            self.fields.pop("avatar_license", None)
            self.fields.pop("get_gravatar", None)
        elif "avatar" in self.fields:
            self.fields["avatar"].required = False
            self.fields["avatar"].widget.is_required = False
        if self.is_bound and not self.is_valid() and "availabilities" in self.errors:
            # Replace self.data with a version that uses initial["availabilities"]
            # in order to have event and timezone data available
            self.data = self.data.copy()
            self.data["availabilities"] = self.initial["availabilities"]

    @cached_property
    def user_fields(self):
        if self.user and not self.essential_only:
            return [
                field
                for field in self.USER_FIELDS
                if field != "email" or self.with_email
            ]
        return [
            field
            for field in self.USER_FIELDS
            if field not in self.FIRST_TIME_EXCLUDE
            and (field != "email" or self.with_email)
        ]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        qs = User.objects.all()
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.filter(email__iexact=email):
            raise ValidationError(EMAIL_ADDRESS_ERROR)
        return email

    def clean(self):
        data = super().clean()
        if (
            self.event.cfp.require_avatar
            and not data.get("avatar")
            and not data.get("get_gravatar")
            and not (self.user and self.user.has_avatar)
        ):
            self.add_error(
                "avatar",
                forms.ValidationError(
                    _(
                        "Please provide a profile picture or allow us to load your picture from gravatar!"
                    )
                ),
            )
        return data

    def save(self, **kwargs):
        for user_attribute in self.user_fields:
            value = self.cleaned_data.get(user_attribute)
            if user_attribute == "avatar":
                if value is False:
                    self.user.avatar = None
                elif value:
                    self.user.avatar = value
            elif value is None and user_attribute == "get_gravatar":
                self.user.get_gravatar = False
            else:
                setattr(self.user, user_attribute, value)
            self.user.save(update_fields=[user_attribute])

        self.instance.event = self.event
        self.instance.user = self.user
        result = super().save(**kwargs)

        if self.user.avatar and "avatar" in self.changed_data:
            self.user.process_image("avatar", generate_thumbnail=True)
        return result

    class Meta:
        model = SpeakerProfile
        fields = ("biography",)
        public_fields = ["name", "biography", "avatar"]
        widgets = {
            "biography": MarkdownWidget,
            "avatar_source": MarkdownWidget,
            "avatar_license": MarkdownWidget,
        }
        field_classes = {
            "avatar": ImageField,
        }
        field_classes = {
            "avatar": ImageField,
        }
        request_require = {"biography", "availabilities"}


class OrgaProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("name", "locale")


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


class SpeakerInformationForm(I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields["limit_types"].queryset = event.submission_types.all()
        if not event.get_feature_flag("use_tracks"):
            self.fields.pop("limit_tracks")
        else:
            self.fields["limit_tracks"].queryset = event.tracks.all()

    def save(self, *args, **kwargs):
        self.instance.event = self.event
        return super().save(*args, **kwargs)

    class Meta:
        model = SpeakerInformation
        fields = (
            "title",
            "text",
            "target_group",
            "limit_types",
            "limit_tracks",
            "resource",
        )
        field_classes = {
            "limit_tracks": SafeModelMultipleChoiceField,
            "limit_types": SafeModelMultipleChoiceField,
            "resource": SizeFileField,
        }
        widgets = {
            "limit_tracks": EnhancedSelectMultiple(color_field="color"),
            "limit_types": EnhancedSelectMultiple,
        }


class SpeakerFilterForm(forms.Form):
    default_renderer = InlineFormRenderer

    role = forms.ChoiceField(
        choices=(
            ("", phrases.base.all_choices),
            ("true", phrases.schedule.speakers),
            ("false", _("Non-accepted submitters")),
        ),
        required=False,
    )
    question = SafeModelChoiceField(
        queryset=Question.objects.none(), required=False, widget=forms.HiddenInput()
    )

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields["question"].queryset = event.questions.all()

    def filter_queryset(self, queryset):
        data = self.cleaned_data
        if data.get("role") == "true":
            queryset.filter(
                user__submissions__in=self.event.submissions.filter(
                    state__in=SubmissionStates.accepted_states
                )
            )
        elif data.get("role") == "false":
            queryset.exclude(
                user__submissions__in=self.event.submissions.filter(
                    state__in=SubmissionStates.accepted_states
                )
            )
        return queryset


class UserSpeakerFilterForm(forms.Form):
    default_renderer = InlineFormRenderer

    role = forms.ChoiceField(
        choices=(
            ("speaker", phrases.schedule.speakers),
            ("submitter", _("Non-accepted submitters")),
            ("all", phrases.base.all_choices),
        ),
        required=False,
        widget=EnhancedSelect,
    )
    events = SafeModelMultipleChoiceField(
        queryset=Event.objects.none(),
        required=False,
        widget=EnhancedSelectMultiple,
    )

    def __init__(self, *args, events=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = events
        if events.count() > 1:
            self.fields["events"].queryset = events
        else:
            self.fields.pop("events")

    def filter_queryset(self, queryset):
        data = self.cleaned_data
        events = data.get("events") or self.events
        role = data.get("role") or "speaker"

        qs = (
            queryset.filter(profiles__event__in=events)
            .prefetch_related("profiles", "profiles__event")
            .annotate(
                submission_count=Count(
                    "submissions",
                    filter=Q(submissions__event__in=events),
                    distinct=True,
                ),
                accepted_submission_count=Count(
                    "submissions",
                    filter=Q(submissions__event__in=events)
                    & Q(submissions__state__in=SubmissionStates.accepted_states),
                    distinct=True,
                ),
            )
        )
        if role == "speaker":
            qs = qs.filter(accepted_submission_count__gt=0)
        elif role == "submitter":
            qs = qs.filter(accepted_submission_count=0)
        qs = qs.order_by("id").distinct()
        return qs
