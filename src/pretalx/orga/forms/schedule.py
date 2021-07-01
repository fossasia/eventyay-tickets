from django import forms
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.orga.forms.export import ExportForm
from pretalx.schedule.models import Schedule
from pretalx.submission.models.submission import Submission, SubmissionStates


class ScheduleReleaseForm(I18nModelForm):
    notify_speakers = forms.BooleanField(
        label=_("Notify speakers of changes"), required=False, initial=True
    )

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields["version"].required = True
        self.fields["comment"].widget.attrs["rows"] = 4
        if not self.event.current_schedule:
            self.fields["comment"].initial = _("We released our first schedule!")
        else:
            self.fields["comment"].initial = _("We released a new schedule version!")

    def clean_version(self):
        version = self.cleaned_data.get("version")
        if self.event.schedules.filter(version__iexact=version).exists():
            raise forms.ValidationError(
                _(
                    "This schedule version was used already, please choose a different one."
                )
            )
        return version

    class Meta:
        model = Schedule
        fields = (
            "version",
            "comment",
        )


class ScheduleExportForm(ExportForm):
    target = forms.MultipleChoiceField(
        required=True,
        label=_("Target group"),
        choices=[("all", _("All proposals"))] + SubmissionStates.valid_choices,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Submission
        model_fields = [
            "title",
            "state",
            "submission_type",
            "track",
            "created",
            "tags",
            "abstract",
            "description",
            "notes",
            "internal_notes",
            "duration",
            "slot_count",
            "content_locale",
            "is_featured",
            "do_not_record",
            "image",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["speaker_ids"] = forms.BooleanField(
            required=False,
            label=_("Speaker IDs"),
            help_text=_(
                "The unique ID of a speaker is used in the speaker URL and in exports"
            ),
        )
        self.fields["speaker_names"] = forms.BooleanField(
            required=False,
            label=_("Speaker names"),
        )
        self.fields["room"] = forms.BooleanField(
            required=False,
            label=_("Room"),
            help_text=_("The room this talk is scheduled in, if any"),
        )
        self.fields["start"] = forms.BooleanField(
            required=False,
            label=_("Start"),
            help_text=_("When the talk starts, if it is currently scheduled"),
        )
        self.fields["end"] = forms.BooleanField(
            required=False,
            label=_("End"),
            help_text=_("When the talk ends, if it is currently scheduled"),
        )
        self.fields["median_score"] = forms.BooleanField(
            required=False,
            label=_("Median score"),
            help_text=_("Median review score, if there have been reviews yet"),
        )

    @cached_property
    def questions(self):
        return self.event.questions.filter(
            target="submission", active=True
        ).prefetch_related("answers", "answers__submission", "options")

    @cached_property
    def filename(self):
        return f"{self.event.slug}_sessions"

    @cached_property
    def export_field_names(self):
        return self.Meta.model_fields + [
            "speaker_ids",
            "speaker_names",
            "room",
            "start",
            "end",
            "median_score",
        ]

    def get_queryset(self):
        target = self.cleaned_data.get("target")
        queryset = self.event.submissions
        if "all" not in target:
            queryset = queryset.filter(state__in=target)
        return (
            queryset.prefetch_related("tags")
            .select_related("submission_type", "track")
            .order_by("code")
        )

    def get_answer(self, question, obj):
        return question.answers.filter(submission=obj).first()

    def _get_speaker_ids_value(self, obj):
        return list(obj.speakers.all().values_list("code", flat=True))

    def _get_speaker_names_value(self, obj):
        return list(obj.speakers.all().values_list("name", flat=True))

    def _get_room_value(self, obj):
        slot = obj.slot
        if slot and slot.room:
            return slot.room.name

    def _get_start_value(self, obj):
        slot = obj.slot
        if slot and slot.start:
            return slot.start.isoformat()

    def _get_end_value(self, obj):
        slot = obj.slot
        if slot and slot.real_end:
            return slot.real_end.isoformat()

    def _get_duration_value(self, obj):
        return obj.get_duration()

    def _get_image_value(self, obj):
        return obj.image_url

    def _get_created_value(self, obj):
        return obj.created.isoformat() if obj.created else None

    def _get_submission_type_value(self, obj):
        return obj.submission_type.name if obj.submission_type else None

    def _get_track_value(self, obj):
        return obj.track.name if obj.track else None

    def _get_tags_value(self, obj):
        return [tag.tag for tag in obj.tags.all()] or None
