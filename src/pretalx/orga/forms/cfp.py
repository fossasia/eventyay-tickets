from django import forms
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.submission.models import (
    AnswerOption,
    CfP,
    Question,
    SubmissionType,
    SubmitterAccessCode,
    Track,
)


class CfPSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    use_tracks = forms.BooleanField(
        label=_("Use tracks"),
        required=False,
        help_text=_("Do you organise your talks by tracks?"),
    )
    present_multiple_times = forms.BooleanField(
        label=_("Slot Count"),
        required=False,
        help_text=_("Can talks be held multiple times?"),
    )
    cfp_show_deadline = forms.BooleanField(
        label=_("Display deadline publicly"),
        required=False,
        help_text=_("Show the time and date the CfP ends to potential speakers."),
    )
    cfp_request_abstract = forms.BooleanField(label="", required=False)
    cfp_request_description = forms.BooleanField(label="", required=False)
    cfp_request_notes = forms.BooleanField(label="", required=False)
    cfp_request_biography = forms.BooleanField(label="", required=False)
    cfp_request_avatar = forms.BooleanField(label="", required=False)
    cfp_request_availabilities = forms.BooleanField(label="", required=False)
    cfp_request_do_not_record = forms.BooleanField(label="", required=False)
    cfp_request_image = forms.BooleanField(label="", required=False)
    cfp_request_track = forms.BooleanField(label="", required=False)
    cfp_request_duration = forms.BooleanField(label="", required=False)
    cfp_require_abstract = forms.BooleanField(label="", required=False)
    cfp_require_description = forms.BooleanField(label="", required=False)
    cfp_require_notes = forms.BooleanField(label="", required=False)
    cfp_require_biography = forms.BooleanField(label="", required=False)
    cfp_require_avatar = forms.BooleanField(label="", required=False)
    cfp_require_availabilities = forms.BooleanField(label="", required=False)
    cfp_require_image = forms.BooleanField(label="", required=False)
    cfp_require_track = forms.BooleanField(label="", required=False)
    cfp_require_duration = forms.BooleanField(label="", required=False)
    cfp_title_min_length = forms.IntegerField(label="", required=False, min_value=0)
    cfp_abstract_min_length = forms.IntegerField(
        label=_("Minimum length"), required=False, min_value=0
    )
    cfp_description_min_length = forms.IntegerField(
        label=_("Minimum length"), required=False, min_value=0
    )
    cfp_biography_min_length = forms.IntegerField(
        label=_("Minimum length"), required=False, min_value=0
    )
    cfp_title_max_length = forms.IntegerField(label="", required=False, min_value=0)
    cfp_abstract_max_length = forms.IntegerField(
        label=_("Maximum length"), required=False, min_value=0
    )
    cfp_description_max_length = forms.IntegerField(
        label=_("Maximum length"), required=False, min_value=0
    )
    cfp_biography_max_length = forms.IntegerField(
        label=_("Maximum length"), required=False, min_value=0
    )
    cfp_count_length_in = forms.ChoiceField(
        label=_("Count text length in"),
        choices=(("chars", _("Characters")), ("words", _("Words"))),
        widget=forms.RadioSelect(),
    )
    mail_on_new_submission = forms.BooleanField(
        label=_("Send mail on new submission"),
        help_text=_(
            "If this setting is checked, you will receive an email to the organiser address for every received submission."
        ),
        required=False,
    )

    def __init__(self, obj, *args, **kwargs):
        kwargs.pop(
            "read_only"
        )  # added in ActionFromUrl view mixin, but not needed here.
        super().__init__(*args, obj=obj, **kwargs)
        if getattr(obj, "email"):
            self.fields[
                "mail_on_new_submission"
            ].help_text += f' (<a href="mailto:{obj.email}">{obj.email}</a>)'
        for field in ["abstract", "description", "biography"]:
            self.fields[f"cfp_{field}_min_length"].widget.attrs["placeholder"] = ""
            self.fields[f"cfp_{field}_max_length"].widget.attrs["placeholder"] = ""


class CfPForm(ReadOnlyFlag, I18nModelForm):
    class Meta:
        model = CfP
        fields = ["headline", "text", "deadline"]
        widgets = {
            "deadline": forms.DateTimeInput(attrs={"class": "datetimepickerfield"})
        }


class QuestionForm(ReadOnlyFlag, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if not (
            event.settings.use_tracks
            and event.tracks.all().count()
            and event.settings.cfp_request_track
        ):
            self.fields.pop("tracks")
        else:
            self.fields["tracks"].queryset = event.tracks.all()
        if not event.submission_types.count():
            self.fields.pop("submission_types")
        else:
            self.fields["submission_types"].queryset = event.submission_types.all()
        if (
            instance
            and instance.pk
            and instance.answers.count()
            and not instance.is_public
        ):
            self.fields["is_public"].disabled = True

    class Meta:
        model = Question
        fields = [
            "target",
            "question",
            "help_text",
            "variant",
            "is_public",
            "is_visible_to_reviewers",
            "required",
            "tracks",
            "submission_types",
            "contains_personal_data",
            "min_length",
            "max_length",
        ]
        field_classes = {
            "variant": SafeModelChoiceField,
            "tracks": SafeModelMultipleChoiceField,
            "submission_types": SafeModelMultipleChoiceField,
        }


class AnswerOptionForm(ReadOnlyFlag, I18nModelForm):
    class Meta:
        model = AnswerOption
        fields = ["answer"]


class SubmissionTypeForm(ReadOnlyFlag, I18nModelForm):
    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        if instance.pk and "duration" in self.changed_data:
            instance.update_duration()

    class Meta:
        model = SubmissionType
        fields = ("name", "default_duration", "deadline", "requires_access_code")
        widgets = {
            "deadline": forms.DateTimeInput(attrs={"class": "datetimepickerfield"})
        }


class TrackForm(ReadOnlyFlag, I18nModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color"].widget.attrs["class"] = "colorpickerfield"

    class Meta:
        model = Track
        fields = ("name", "color", "requires_access_code")


class SubmitterAccessCodeForm(forms.ModelForm):
    def __init__(self, *args, event, **kwargs):
        self.event = event
        initial = kwargs.get("initial", {})
        if not kwargs.get("instance"):
            initial["code"] = SubmitterAccessCode().generate_code()
            initial["valid_until"] = event.cfp.deadline
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)
        self.fields["submission_type"].queryset = SubmissionType.objects.filter(
            event=self.event
        )
        if event.settings.use_tracks:
            self.fields["track"].queryset = Track.objects.filter(event=self.event)
        else:
            self.fields.pop("track")

    class Meta:
        model = SubmitterAccessCode
        fields = (
            "code",
            "valid_until",
            "maximum_uses",
            "track",
            "submission_type",
        )
        field_classes = {
            "track": SafeModelChoiceField,
            "submission_type": SafeModelChoiceField,
        }
        widgets = {
            "valid_until": forms.DateTimeInput(attrs={"class": "datetimepickerfield"})
        }


class AccessCodeSendForm(forms.Form):
    to = forms.EmailField(label=_("To"))
    subject = forms.CharField(label=_("Subject"))
    text = forms.CharField(widget=forms.Textarea(), label=_("Text"))

    def __init__(self, *args, instance, user, **kwargs):
        self.access_code = instance
        subject = _("Access code for the {event} CfP").format(event=instance.event.name)
        text = (
            str(
                _(
                    """Hi!

This is an access code for the {event} CfP."""
                ).format(event=instance.event.name)
            )
            + " "
        )
        if instance.track:
            text += (
                str(
                    _(
                        "It will allow you to submit a proposal to the “{track}” track."
                    ).format(track=instance.track.name)
                )
                + " "
            )
        else:
            text += str(_("It will allow you to submit a proposal to our CfP.")) + " "
        if instance.valid_until:
            text += (
                str(
                    _("This access code is valid until {date}.").format(
                        date=instance.valid_until.strftime("%Y-%m-%d %H:%M")
                    )
                )
                + " "
            )
        if (
            instance.maximum_uses
            and instance.maximum_uses != 1
            and instance.maximum_uses - instance.redeemed > 1
        ):
            text += str(
                _("The code can be redeemed multiple times ({num}).").format(
                    num=instance.redemptions_left
                )
            )
        text += _(
            """
Please follow this URL to use the code:

  {url}

I'm looking forward to your submission!
{name}"""
        ).format(url=instance.urls.cfp_url.full(), name=user.get_display_name(),)
        initial = kwargs.get("intial", {})
        initial["subject"] = f"[{instance.event.slug}] {subject}"
        initial["text"] = text
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)

    def save(self):
        self.access_code.send_invite(
            to=self.cleaned_data["to"].strip(),
            subject=self.cleaned_data["subject"],
            text=self.cleaned_data["text"],
        )
