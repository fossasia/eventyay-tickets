import json

from django import forms
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField
from i18nfield.forms import I18nFormMixin, I18nModelForm
from i18nfield.strings import LazyI18nString

from pretalx.common.mixins.forms import I18nHelpText, JsonSubfieldMixin, ReadOnlyFlag
from pretalx.submission.models import (
    AnswerOption,
    Question,
    QuestionVariant,
    SubmissionType,
    SubmitterAccessCode,
    Track,
)
from pretalx.submission.models.cfp import CfP, default_fields
from pretalx.submission.models.question import QuestionRequired


class CfPSettingsForm(
    ReadOnlyFlag, I18nFormMixin, I18nHelpText, JsonSubfieldMixin, forms.Form
):
    use_tracks = forms.BooleanField(
        label=_("Use tracks"),
        required=False,
        help_text=_("Do you organise your sessions by tracks?"),
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
            "additional_speaker",
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
                initial=obj.cfp.fields.get(attribute, default_fields()[attribute])[
                    "visibility"
                ],
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
            if key not in self.instance.cfp.fields:
                self.instance.cfp.fields[key] = default_fields()[key]
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
    options = forms.FileField(
        label=_("Upload options"),
        help_text=_(
            "You can upload question options here, one option per line. "
            "To use multiple languages, please upload a JSON file with a list of "
            "options:"
        )
        + ' <code>[{"en": "English", "de": "Deutsch"}, ...]</code>',
        required=False,
    )
    options_replace = forms.BooleanField(
        label=_("Replace existing options"),
        help_text=_(
            "If you upload new options, do you want to replace the existing ones? "
            "Please note that this will DELETE all existing answers to this question! "
            "If you do not check this, the uploaded options will be added to the "
            "existing ones, without adding duplicates."
        ),
        required=False,
    )

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if not (
            event.feature_flags["use_tracks"]
            and event.tracks.all().count()
            and event.cfp.request_track
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

    def clean_options(self):
        # read uploaded file, return list of strings or list of i18n strings
        options = self.cleaned_data.get("options")
        if not options:
            return
        try:
            content = options.read().decode("utf-8")
        except Exception:
            raise forms.ValidationError(_("Could not read file."))

        try:
            options = json.loads(content)
            if not isinstance(options, list):
                raise Exception(_("JSON file does not contain a list."))
            if not all(isinstance(o, dict) for o in options):
                raise Exception(_("JSON file does not contain a list of objects."))
            return [LazyI18nString(data=o) for o in options]
        except Exception:
            options = content.split("\n")
            options = [o.strip() for o in options if o.strip()]
            return options

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
        options = self.cleaned_data.get("options")
        options_replace = self.cleaned_data.get("options_replace")
        if options_replace and not options:
            self.add_error(
                "options_replace",
                forms.ValidationError(
                    _("You cannot replace answer options without uploading new ones.")
                ),
            )

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        options = self.cleaned_data.get("options")
        options_replace = self.cleaned_data.get("options_replace")
        if not options:
            return instance
        if options_replace:
            instance.answers.all().delete()
            instance.options.all().delete()
            for option in options:
                instance.options.create(answer=option)
            return instance

        # If we aren't replacing all existing options, we need to make sure
        # we don't add duplicates.
        existing_options = list(instance.options.all().values_list("answer", flat=True))
        use_i18n = (
            isinstance(options[0], LazyI18nString) and instance.event.is_multilingual
        )
        if not use_i18n:
            # Monolangual i18n strings with strings aren't equal, so we're normalising.
            with override(instance.event.locale):
                existing_options = [str(o) for o in existing_options]
                options = [str(o) for o in options]
        new_options = []
        for option in options:
            if option not in existing_options:
                new_options.append(AnswerOption(question=instance, answer=option))
        AnswerOption.objects.bulk_create(new_options)

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
            "min_number",
            "max_number",
            "min_date",
            "max_date",
            "min_datetime",
            "max_datetime",
        ]
        widgets = {
            "deadline": forms.DateTimeInput(attrs={"class": "datetimepickerfield"}),
            "question_required": forms.RadioSelect(),
            "freeze_after": forms.DateTimeInput(attrs={"class": "datetimepickerfield"}),
            "min_datetime": forms.DateTimeInput(attrs={"class": "datetimepickerfield"}),
            "max_datetime": forms.DateTimeInput(attrs={"class": "datetimepickerfield"}),
            "min_date": forms.DateInput(attrs={"class": "datepickerfield"}),
            "max_date": forms.DateInput(attrs={"class": "datepickerfield"}),
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
        if self.instance.pk:
            url = f"{event.cfp.urls.new_access_code}?track={self.instance.pk}"
            self.fields["requires_access_code"].help_text += " " + _(
                'You can create an access code <a href="{url}">here</a>.'
            ).format(url=url)

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
            initial["code"] = SubmitterAccessCode.generate_code()
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
