from django import forms
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.forms.mixins import I18nHelpText
from pretalx.common.forms.renderers import InlineFormRenderer
from pretalx.common.forms.widgets import EnhancedSelectMultiple
from pretalx.common.text.phrases import phrases
from pretalx.orga.forms.export import ExportForm
from pretalx.schedule.models import Schedule, TalkSlot
from pretalx.schedule.utils import guess_schedule_version
from pretalx.submission.models.submission import Submission, SubmissionStates


class ScheduleReleaseForm(I18nHelpText, I18nModelForm):
    default_renderer = InlineFormRenderer

    notify_speakers = forms.BooleanField(
        label=_("Notify speakers of changes"), required=False, initial=True
    )

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields["version"].required = True
        self.fields["comment"].widget.attrs["rows"] = 4
        url = self.event.update_template.urls.base
        self.fields["notify_speakers"].help_text = (
            f"<a href='{url}'>{_('Email template')}</a>"
        )
        if not self.event.current_schedule:
            self.fields["comment"].initial = phrases.schedule.first_schedule
        else:
            self.fields["comment"].initial = _("We released a new schedule version!")
        if not self.fields["version"].initial:
            self.fields["version"].initial = guess_schedule_version(self.event)

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
        choices=[("all", phrases.base.all_choices)]
        + [
            (state, name)
            for (state, name) in SubmissionStates.valid_choices
            if state != SubmissionStates.DRAFT
        ],
        widget=EnhancedSelectMultiple(color_field=SubmissionStates.get_color),
    )

    class Meta:
        model = Submission
        model_fields = [
            "title",
            "state",
            "pending_state",
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
            label=TalkSlot._meta.get_field("room").verbose_name,
            help_text=TalkSlot._meta.get_field("room").help_text,
        )
        self.fields["start"] = forms.BooleanField(
            required=False,
            label=TalkSlot._meta.get_field("start").verbose_name,
            help_text=TalkSlot._meta.get_field("start").help_text,
        )
        self.fields["start_date"] = forms.BooleanField(
            required=False,
            label=TalkSlot._meta.get_field("start").verbose_name
            + " ("
            + _("date")
            + ")",
            help_text=TalkSlot._meta.get_field("start").help_text,
        )
        self.fields["start_time"] = forms.BooleanField(
            required=False,
            label=TalkSlot._meta.get_field("start").verbose_name
            + " ("
            + _("time")
            + ")",
            help_text=TalkSlot._meta.get_field("start").help_text,
        )
        self.fields["end"] = forms.BooleanField(
            required=False,
            label=TalkSlot._meta.get_field("end").verbose_name,
            help_text=TalkSlot._meta.get_field("end").help_text,
        )
        self.fields["end_date"] = forms.BooleanField(
            required=False,
            label=TalkSlot._meta.get_field("end").verbose_name + " (" + _("date") + ")",
            help_text=TalkSlot._meta.get_field("end").help_text,
        )
        self.fields["end_time"] = forms.BooleanField(
            required=False,
            label=TalkSlot._meta.get_field("end").verbose_name + " (" + _("time") + ")",
            help_text=TalkSlot._meta.get_field("end").help_text,
        )
        self.fields["median_score"] = forms.BooleanField(
            required=False,
            label=_("Median score"),
            help_text=_("Median review score, if there have been reviews yet"),
        )
        self.fields["mean_score"] = forms.BooleanField(
            required=False,
            label=_("Average (mean) score"),
            help_text=_("Average review score, if there have been reviews yet"),
        )
        self.fields["resources"] = forms.BooleanField(
            required=False,
            label=_("Resources"),
            help_text=_(
                "Resources provided by the speaker, either as links or as uploaded files"
            ),
        )

    @cached_property
    def questions(self):
        return self.event.questions.filter(
            target="submission",
        ).prefetch_related(
            "answers", "answers__submission", "options", "answers__options"
        )

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
            "start_date",
            "start_time",
            "end",
            "end_date",
            "end_time",
            "median_score",
            "mean_score",
            "resources",
        ]

    def get_queryset(self):
        target = self.cleaned_data.get("target")
        queryset = self.event.submissions
        if "all" not in target:
            queryset = queryset.filter(state__in=target)
        return (
            queryset.prefetch_related("tags")
            .select_related("submission_type", "track")
            .prefetch_related("resources")
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

    def _get_start(self, obj):
        slot = obj.slot
        if slot and slot.start:
            return slot.local_start

    def _get_end(self, obj):
        slot = obj.slot
        if slot and slot.real_end:
            return slot.local_end

    def _get_start_date_value(self, obj):
        start = self._get_start(obj)
        return start.date().isoformat() if start else None

    def _get_start_time_value(self, obj):
        start = self._get_start(obj)
        return start.time().isoformat() if start else None

    def _get_end_date_value(self, obj):
        end = self._get_end(obj)
        return end.date().isoformat() if end else None

    def _get_end_time_value(self, obj):
        end = self._get_end(obj)
        return end.time().isoformat() if end else None

    def _get_start_value(self, obj):
        start = self._get_start(obj)
        return start.isoformat() if start else None

    def _get_end_value(self, obj):
        end = self._get_end(obj)
        return end.isoformat() if end else None

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

    def _get_resources_value(self, obj):
        return [resource.url for resource in obj.active_resources if resource.url]
