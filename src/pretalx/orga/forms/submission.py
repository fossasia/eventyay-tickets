import json

from django import forms
from django.utils.translation import gettext as _
from django_scopes.forms import SafeModelChoiceField

from pretalx.common.mixins.forms import ReadOnlyFlag, RequestRequire
from pretalx.submission.models import Submission, SubmissionType


class SubmissionForm(ReadOnlyFlag, RequestRequire, forms.ModelForm):
    def __init__(self, event, anonymise=False, **kwargs):
        self.event = event
        if anonymise:
            kwargs.pop("initial", None)
            initial = {}
            instance = kwargs.pop("instance", None)
            previous_data = instance.anonymised
            for key in self._meta.fields:
                initial[key] = (
                    previous_data.get(key) or getattr(instance, key, None) or ""
                )
            kwargs["initial"] = initial
        super().__init__(**kwargs)
        if "submission_type" in self.fields:
            self.fields["submission_type"].queryset = SubmissionType.objects.filter(
                event=event
            )

        if not self.instance.pk:
            self.fields["speaker"] = forms.EmailField(
                label=_("Speaker email"),
                help_text=_(
                    "The email address of the speaker holding the talk. They will be invited to create an account."
                ),
            )
            self.fields["speaker_name"] = forms.CharField(
                label=_("Speaker name"),
                help_text=_(
                    "The name of the speaker that should be displayed publicly."
                ),
            )
        if "abstract" in self.fields:
            self.fields["abstract"].widget.attrs["rows"] = 2
        if not event.settings.present_multiple_times:
            self.fields.pop("slot_count", None)
        if not event.settings.use_tracks:
            self.fields.pop("track", None)
        elif "track" in self.fields:
            self.fields["track"].queryset = event.tracks.all()

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        if instance.pk and "duration" in self.changed_data:
            instance.update_duration()
        if "slot_count" in self.changed_data and "slot_count" in self.initial:
            instance.update_talk_slots()
        return instance

    class Meta:
        model = Submission
        fields = [
            "title",
            "submission_type",
            "track",
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
        field_classes = {
            "submission_type": SafeModelChoiceField,
            "track": SafeModelChoiceField,
        }
        request_require = {
            "title",
            "abstract",
            "description",
            "notes",
            "image",
            "do_not_record",
        }


class AnonymiseForm(SubmissionForm):
    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        if not instance or not instance.pk:
            raise Exception("Cannot anonymise unsaved submission.")
        kwargs["event"] = instance.event
        kwargs["anonymise"] = True
        super().__init__(*args, **kwargs)
        self._instance = instance
        to_be_removed = []
        for key, field in self.fields.items():
            if not getattr(instance, key, None):
                to_be_removed.append(key)
            else:
                field.plaintext = getattr(self._instance, key)
                field.required = False
        for key in to_be_removed:
            self.fields.pop(key)

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
