from django import forms
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.mixins.forms import I18nHelpText, JsonSubfieldMixin, ReadOnlyFlag
from pretalx.submission.models import (
    AnswerOption,
    CfP,
    Question,
    QuestionVariant,
    SubmissionType,
    SubmitterAccessCode,
    Track,
)
from pretalx.submission.models.question import QuestionRequired


class CfPSettingsForm(
    ReadOnlyFlag, I18nFormMixin, I18nHelpText, JsonSubfieldMixin, forms.Form
):
    use_tracks = forms.BooleanField(
        label=_("Use tracks"),
        required=False,
        help_text=_("Do you organise your sessions by tracks?"),
    )
    use_gravatar = forms.BooleanField(
        label=_("Use Gravatar"),
        required=False,
        help_text=_(
            "Allow speakers to automatically include their gravatar profile image."
        ),
    )
    present_multiple_times = forms.BooleanField(
        label=_("Slot Count"),
        required=False,
        help_text=_("Can sessions be held multiple times?"),
    )
    mail_on_new_submission = forms.BooleanField(
        label=_("Send mail on new proposal"),
        help_text=_(
            "If this setting is checked, you will receive an email to the organiser address for every received proposal."
        ),
        required=False,
    )

    def __init__(self, *args, obj, **kwargs):
        kwargs.pop(
            "read_only"
        )  # added in ActionFromUrl view mixin, but not needed here.
        self.instance = obj
        super().__init__(*args, **kwargs)
        if getattr(obj, "email", None):
            self.fields[
                "mail_on_new_submission"
            ].help_text += f' (<a href="mailto:{obj.email}">{obj.email}</a>)'
        self.length_fields = ["title", "abstract", "description", "biography"]
        self.request_require_fields = [
            "abstract",
            "description",
            "notes",
            "biography",
            "avatar",
            "availabilities",
            "do_not_record",
            "image",
            "track",
            "duration",
            "content_locale",
        ]
        for attribute in self.length_fields:
            field_name = f"cfp_{attribute}_min_length"
            self.fields[field_name] = forms.IntegerField(
                required=False,
                min_value=0,
                initial=obj.cfp.fields[attribute].get("min_length"),
            )
            self.fields[field_name].widget.attrs["placeholder"] = ""
            field_name = f"cfp_{attribute}_max_length"
            self.fields[field_name] = forms.IntegerField(
                required=False,
                min_value=0,
                initial=obj.cfp.fields[attribute].get("max_length"),
            )
            self.fields[field_name].widget.attrs["placeholder"] = ""
        for attribute in self.request_require_fields:
            field_name = f"cfp_ask_{attribute}"
            self.fields[field_name] = forms.ChoiceField(
                required=True,
                initial=obj.cfp.fields[attribute]["visibility"],
                choices=[
                    ("do_not_ask", _("Do not ask")),
                    ("optional", _("Ask, but do not require input")),
                    ("required", _("Ask and require input")),
                ],
            )
        if not obj.is_multilingual:
            self.fields.pop("cfp_ask_content_locale", None)

    def save(self, *args, **kwargs):
        for key in self.request_require_fields:
            self.instance.cfp.fields[key]["visibility"] = self.cleaned_data.get(
                f"cfp_ask_{key}"
            )
        for key in self.length_fields:
            self.instance.cfp.fields[key]["min_length"] = self.cleaned_data.get(
                f"cfp_{key}_min_length"
            )
            self.instance.cfp.fields[key]["max_length"] = self.cleaned_data.get(
                f"cfp_{key}_max_length"
            )
        self.instance.cfp.save()
        super().save(*args, **kwargs)

    class Meta:
        # These are JSON fields on event.settings
        json_fields = {
            "use_tracks": "feature_flags",
            "use_gravatar": "feature_flags",
            "present_multiple_times": "feature_flags",
            "mail_on_new_submission": "mail_settings",
        }


class CfPForm(ReadOnlyFlag, I18nHelpText, JsonSubfieldMixin, I18nModelForm):
    show_deadline = forms.BooleanField(
        label=_("Display deadline publicly"),
        required=False,
        help_text=_("Show the time and date the CfP ends to potential speakers."),
    )
    count_length_in = forms.ChoiceField(
        label=_("Count text length in"),
        choices=(("chars", _("Characters")), ("words", _("Words"))),
        widget=forms.RadioSelect(),
    )

    class Meta:
        model = CfP
        fields = ["headline", "text", "deadline"]
        widgets = {
            "deadline": forms.DateTimeInput(attrs={"class": "datetimepickerfield"})
        }
        # These are JSON fields on cfp.settings
        json_fields = {
            "show_deadline": "settings",
            "count_length_in": "settings",
        }


class QuestionForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if not (
            event.feature_flags["use_tracks"]
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

    def clean(self):
        deadline = self.cleaned_data["deadline"]
        question_required = self.cleaned_data["question_required"]
        if (not deadline) and (question_required == QuestionRequired.AFTER_DEADLINE):
            self.add_error(
                "deadline",
                forms.ValidationError(
                    _(
                        "Please select a deadline after which the question should become mandatory."
                    )
                ),
            )
        if (
            question_required == QuestionRequired.OPTIONAL
            or question_required == QuestionRequired.REQUIRED
        ):
            self.cleaned_data["deadline"] = None

    class Meta:
        model = Question
        fields = [
            "target",
            "question",
            "help_text",
            "question_required",
            "deadline",
            "freeze_after",
            "variant",
            "is_public",
            "is_visible_to_reviewers",
            "tracks",
            "submission_types",
            "contains_personal_data",
            "min_length",
            "max_length",
        ]
        widgets = {
            "deadline": forms.DateTimeInput(attrs={"class": "datetimepickerfield"}),
            "question_required": forms.RadioSelect(),
            "freeze_after": forms.DateTimeInput(attrs={"class": "datetimepickerfield"}),
            "tracks": forms.SelectMultiple(attrs={"class": "select2"}),
            "submission_types": forms.SelectMultiple(attrs={"class": "select2"}),
        }
        field_classes = {
            "variant": SafeModelChoiceField,
            "tracks": SafeModelMultipleChoiceField,
            "submission_types": SafeModelMultipleChoiceField,
        }


class AnswerOptionForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    class Meta:
        model = AnswerOption
        fields = ["answer"]


class SubmissionTypeForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"]
        qs = self.event.submission_types.all()
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if any(str(s.name) == str(name) for s in qs):
            raise forms.ValidationError(
                _("You already have a session type by this name!")
            )
        return name

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


class TrackForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields["color"].widget.attrs["class"] = "colorpickerfield"

    def clean_name(self):
        name = self.cleaned_data["name"]
        qs = self.event.tracks.all()
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if any(str(s.name) == str(name) for s in qs):
            raise forms.ValidationError(_("You already have a track by this name!"))
        return name

    class Meta:
        model = Track
        fields = ("name", "description", "color", "requires_access_code")


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
        if event.feature_flags["use_tracks"]:
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
            "valid_until": forms.DateTimeInput(attrs={"class": "datetimepickerfield"}),
            "track": forms.Select(attrs={"class": "select2"}),
            "submission_type": forms.Select(attrs={"class": "select2"}),
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

I'm looking forward to your proposal!
{name}"""
        ).format(
            url=instance.urls.cfp_url.full(),
            name=user.get_display_name(),
        )
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


class QuestionFilterForm(forms.Form):
    role = forms.ChoiceField(
        choices=(
            ("", _("all")),
            ("accepted", _("Accepted or confirmed speakers")),
            ("confirmed", _("Confirmed speakers")),
        ),
        required=False,
        label=_("Recipients"),
    )
    track = SafeModelChoiceField(Track.objects.none(), required=False)
    submission_type = SafeModelChoiceField(
        SubmissionType.objects.none(), required=False
    )

    def __init__(self, *args, event, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields["submission_type"].queryset = SubmissionType.objects.filter(
            event=event
        )
        if not event.feature_flags["use_tracks"]:
            self.fields.pop("track", None)
        elif "track" in self.fields:
            self.fields["track"].queryset = event.tracks.all()

    def get_submissions(self):
        role = self.cleaned_data["role"]
        track = self.cleaned_data.get("track")
        submission_type = self.cleaned_data["submission_type"]
        talks = self.event.submissions.all()
        if role == "accepted":
            talks = talks.filter(Q(state="accepted") | Q(state="confirmed"))
        elif role == "confirmed":
            talks = talks.filter(state="confirmed")
        if track:
            talks = talks.filter(track=track)
        if submission_type:
            talks = talks.filter(submission_type=submission_type)
        return talks

    def get_question_information(self, question):
        result = {}
        talks = self.get_submissions()
        speakers = self.event.submitters.filter(submissions__in=talks)
        answers = question.answers.filter(
            Q(person__in=speakers) | Q(submission__in=talks)
        )
        result["answer_count"] = answers.count()
        result["missing_answers"] = question.missing_answers(
            filter_speakers=speakers, filter_talks=talks
        )
        if question.variant in [QuestionVariant.CHOICES, QuestionVariant.MULTIPLE]:
            grouped_answers = (
                answers.order_by("options")
                .values("options", "options__answer")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
        elif question.variant == QuestionVariant.FILE:
            grouped_answers = [{"answer": answer, "count": 1} for answer in answers]
        else:
            grouped_answers = (
                answers.order_by("answer")
                .values("answer")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
        result["grouped_answers"] = grouped_answers
        return result


class ReminderFilterForm(QuestionFilterForm):
    questions = SafeModelMultipleChoiceField(
        Question.objects.none(),
        required=False,
        help_text=_("If you select no question, all questions will be used."),
        label=_("Questions"),
    )

    def get_question_queryset(self):
        # We want to exclude questions with "freeze after", the deadlines of which have passed
        return Question.objects.filter(
            event=self.event,
            target__in=["speaker", "submission"],
        ).exclude(freeze_after__lt=timezone.now())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["questions"].queryset = self.get_question_queryset()
