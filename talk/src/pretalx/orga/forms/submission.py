import json

from django import forms
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField

from pretalx.common.forms.fields import ImageField
from pretalx.common.forms.mixins import ReadOnlyFlag, RequestRequire
from pretalx.common.forms.renderers import InlineFormLabelRenderer, InlineFormRenderer
from pretalx.common.forms.widgets import (
    EnhancedSelect,
    EnhancedSelectMultiple,
    HtmlDateTimeInput,
    MarkdownWidget,
    TextInputWithAddon,
)
from pretalx.common.text.phrases import phrases
from pretalx.schedule.models import TalkSlot
from pretalx.submission.models import Submission, SubmissionStates


class SubmissionForm(ReadOnlyFlag, RequestRequire, forms.ModelForm):
    content_locale = forms.ChoiceField(label=phrases.base.language)

    def __init__(self, event, anonymise=False, **kwargs):
        self.event = event
        initial_slot = {}
        instance = kwargs.get("instance")
        if instance and instance.pk:
            slot = (
                instance.slots.filter(schedule__version__isnull=True)
                .select_related("room")
                .filter(start__isnull=False)
                .order_by("start")
                .first()
            )
            if slot:
                initial_slot = {
                    "room": slot.room,
                    "start": (
                        slot.local_start.strftime("%Y-%m-%dT%H:%M")
                        if slot.local_start
                        else ""
                    ),
                    "end": (
                        slot.local_end.strftime("%Y-%m-%dT%H:%M")
                        if slot.real_end
                        else ""
                    ),
                }
        if anonymise:
            kwargs.pop("initial", None)
            initial = {}
            instance = kwargs.pop("instance", None)
            previous_data = instance.anonymised
            for key in self._meta.fields:
                initial[key] = (
                    previous_data.get(key) or getattr(instance, key, None) or ""
                )
                if hasattr(initial[key], "all"):  # Tags, for the moment
                    initial[key] = initial[key].all()
            kwargs["initial"] = initial
        kwargs["initial"] = kwargs.get("initial") or {}
        kwargs["initial"].update(initial_slot)
        super().__init__(**kwargs)
        if "submission_type" in self.fields:
            self.fields["submission_type"].queryset = self.event.submission_types.all()
        if not self.event.tags.all().exists():
            self.fields.pop("tags", None)
        elif "tags" in self.fields:
            self.fields["tags"].queryset = self.event.tags.all()
            self.fields["tags"].required = False

        self.is_creating = False
        if not self.instance.pk:
            self.is_creating = True
            if not anonymise:
                self.fields["state"] = forms.ChoiceField(
                    label=_("Proposal state"),
                    choices=[
                        (choice, name)
                        for (choice, name) in SubmissionStates.get_choices()
                        if choice != SubmissionStates.DELETED
                        and choice != SubmissionStates.DRAFT
                    ],
                    initial=SubmissionStates.SUBMITTED,
                    required=True,
                    widget=EnhancedSelect(color_field=SubmissionStates.get_color),
                )
        if (
            not self.instance.pk
            or self.instance.state in SubmissionStates.accepted_states
        ):
            self.fields["room"] = forms.ModelChoiceField(
                required=False,
                queryset=event.rooms.all(),
                label=TalkSlot._meta.get_field("room").verbose_name,
                initial=initial_slot.get("room"),
                widget=EnhancedSelect,
            )
            self.fields["start"] = forms.DateTimeField(
                required=False,
                label=TalkSlot._meta.get_field("start").verbose_name,
                widget=HtmlDateTimeInput,
                initial=initial_slot.get("start"),
            )
            self.fields["end"] = forms.DateTimeField(
                required=False,
                label=TalkSlot._meta.get_field("end").verbose_name,
                widget=HtmlDateTimeInput,
                initial=initial_slot.get("end"),
            )
        if "abstract" in self.fields:
            self.fields["abstract"].widget.attrs["rows"] = 2
        if not event.get_feature_flag("present_multiple_times"):
            self.fields.pop("slot_count", None)
        if not event.get_feature_flag("use_tracks"):
            self.fields.pop("track", None)
        elif "track" in self.fields:
            self.fields["track"].queryset = event.tracks.all()
        if "content_locale" in self.fields:
            if len(event.content_locales) == 1:
                self.fields.pop("content_locale")
            else:
                self.fields["content_locale"].choices = self.event.named_content_locales
        # If duration is not required, point out that the default is the session type's duration,
        # but only if there is more than one session type, because otherwise users will be
        # confused what that is.
        if (
            "duration" in self.fields
            and not self.fields["duration"].required
            and "submission_type" in self.fields
            and len(self.fields["submission_type"].queryset) > 1
        ):
            self.fields["duration"].help_text += " " + str(
                _("Leave empty to use the default duration for the session type.")
            )

    def clean(self):
        data = super().clean()
        start = data.get("start")
        end = data.get("end")
        if start and end and start > end:
            self.add_error(
                "end",
                forms.ValidationError(
                    _("The end time has to be after the start time."),
                ),
            )
        return data

    def save(self, *args, **kwargs):
        if "content_locale" not in self.fields:
            self.instance.content_locale = self.event.locale
        instance = super().save(*args, **kwargs)
        if self.is_creating:
            instance._set_state(self.cleaned_data["state"], force=True)
        else:
            if "duration" in self.changed_data:
                instance.update_duration()
            if "track" in self.changed_data:
                instance.update_review_scores()
            if "slot_count" in self.changed_data and "slot_count" in self.initial:
                instance.update_talk_slots()
        if (
            instance.state in SubmissionStates.accepted_states
            and self.cleaned_data.get("room")
            and self.cleaned_data.get("start")
            and any(field in self.changed_data for field in ("room", "start", "end"))
        ):
            slot = (
                instance.slots.filter(schedule=instance.event.wip_schedule)
                .order_by("start")
                .first()
            )
            slot.room = self.cleaned_data.get("room")
            slot.start = self.cleaned_data.get("start")
            slot.end = self.cleaned_data.get("end")
            slot.save()
        return instance

    class Meta:
        model = Submission
        fields = [
            "title",
            "submission_type",
            "track",
            "tags",
            "abstract",
            "description",
            "notes",
            "internal_notes",
            "content_locale",
            "do_not_record",
            "duration",
            "slot_count",
            "image",
            "is_featured",
        ]
        widgets = {
            "tags": EnhancedSelectMultiple(color_field="color"),
            "track": EnhancedSelect(color_field="color"),
            "submission_type": EnhancedSelect,
            "abstract": MarkdownWidget,
            "description": MarkdownWidget,
            "notes": MarkdownWidget,
            "duration": TextInputWithAddon(addon_after=_("minutes")),
        }
        field_classes = {
            "submission_type": SafeModelChoiceField,
            "tags": SafeModelMultipleChoiceField,
            "track": SafeModelChoiceField,
            "image": ImageField,
        }
        request_require = {
            "title",
            "abstract",
            "description",
            "notes",
            "image",
            "do_not_record",
            "content_locale",
        }


class AnonymiseForm(SubmissionForm):
    default_renderer = InlineFormRenderer

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        if not instance or not instance.pk:
            raise Exception("Cannot anonymise unsaved submission.")
        kwargs["event"] = instance.event
        kwargs["anonymise"] = True
        super().__init__(*args, **kwargs)
        self._instance = instance
        to_be_removed = ["content_locale"]
        for key, field in self.fields.items():
            try:
                field.plaintext = getattr(self._instance, key)
                field.required = False
            except AttributeError:
                to_be_removed.append(key)
        for key in to_be_removed:
            self.fields.pop(key, None)

    def save(self):
        anonymised_data = {"_anonymised": True}
        for key, value in self.cleaned_data.items():
            if value != getattr(self._instance, key, ""):
                anonymised_data[key] = value
        self._instance.anonymised_data = json.dumps(anonymised_data)
        self._instance.save(update_fields=["anonymised_data"])

    class Meta:
        model = Submission
        fields = [
            "title",
            "abstract",
            "description",
            "notes",
        ]
        request_require = fields


class SubmissionStateChangeForm(forms.Form):
    pending = forms.BooleanField(
        label=_("Mark the new state as “pending”"),
        help_text=_(
            "If you mark state changes as pending, they won’t be visible to speakers right away. You can always apply pending changes for some or all proposals in one go once you’re ready to make your decisions public."
        ),
        required=False,
        initial=False,
    )


class AddSpeakerForm(forms.Form):
    email = forms.EmailField(
        label=phrases.cfp.speaker_email,
        help_text=_(
            "The email address of the speaker holding the session. They will be invited to create an account."
        ),
        required=False,
        widget=forms.Select,
    )
    name = forms.CharField(
        label=_("Speaker name"),
        help_text=_("The name of the speaker that should be displayed publicly."),
        required=False,
    )
    locale = forms.ChoiceField(
        label=_("Invite language"),
        choices=[],
        required=False,
        help_text=_(
            "The language in which the speaker will receive their invitation email."
        ),
        widget=EnhancedSelect,
    )

    def __init__(self, *args, event=None, form_renderer=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not event.named_locales or len(event.named_locales) < 2:
            self.fields.pop("locale")
        else:
            self.fields["locale"].choices = event.named_locales
            self.fields["locale"].initial = event.locale

    def clean(self):
        data = super().clean()
        if data.get("name") and not data.get("email"):
            raise forms.ValidationError(_("Please provide an email address."))
        return data


class AddSpeakerInlineForm(AddSpeakerForm):
    default_renderer = InlineFormLabelRenderer
