import json
from io import StringIO

from defusedcsv import csv
from django import forms
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from i18nfield.utils import I18nJSONEncoder

from pretalx.submission.models.question import Answer


class SpeakerExportForm(forms.Form):
    target = forms.ChoiceField(
        required=True,
        label=_("Target group"),
        choices=(
            ("all", _("All submitters")),
            ("accepted", _("With accepted proposals")),
            ("confirmed", _("With confirmed proposals")),
            ("rejected", _("With rejected proposals")),
        ),
        widget=forms.RadioSelect,
    )
    export_format = forms.ChoiceField(
        required=True,
        label=_("Export format"),
        help_text=_(
            "A CSV export can be opened directly in Excel and similar applications."
        ),
        choices=(
            ("csv", _("CSV export")),
            ("json", _("JSON export")),
        ),
        widget=forms.RadioSelect,
    )
    data_delimiter = forms.ChoiceField(
        required=False,
        label=_("Data delimiter"),
        help_text=_(
            "How do you want to separate data within a single cell (for example, multiple speakers in one session)?"
        ),
        choices=(
            ("newline", _("Newline")),
            ("comma", _("Comma")),
        ),
        widget=forms.RadioSelect,
    )
    name = forms.BooleanField(
        required=False,
        label=_("Name"),
    )
    email = forms.BooleanField(
        required=False,
        label=_("E-Mail"),
    )
    biography = forms.BooleanField(
        required=False,
        label=_("Biography"),
    )
    avatar = forms.BooleanField(
        required=False,
        label=_("Picture"),
        help_text=_("The link to the speaker's profile picture"),
    )
    submission_ids = forms.BooleanField(
        required=False,
        label=_("Proposal IDs"),
        help_text=_(
            "The unique ID of a proposal is used in the proposal URL and in exports"
        ),
    )
    submission_titles = forms.BooleanField(
        required=False,
        label=_("Proposal Titles"),
    )

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.questions = event.questions.filter(target="speaker", active=True)
        self.question_field_names = [
            f"question_{question.pk}" for question in self.questions
        ]
        for question in self.questions:
            self.fields[f"question_{question.pk}"] = forms.BooleanField(
                required=False,
                label=str(_("Answer to the question '{q}'")).format(
                    q=question.question
                ),
            )

    def clean(self):
        data = super().clean()
        if data.get("export_format") == "csv" and not data.get("data_delimiter"):
            raise forms.ValidationError(
                _("Please select a delimiter for your CSV export.")
            )
        return data

    @property
    def export_field_names(self):
        return [
            "name",
            "email",
            "biography",
            "avatar",
            "submission_ids",
            "submission_titles",
        ]

    @property
    def export_fields(self):
        result = [
            forms.BoundField(self, self.fields[field], field)
            for field in self.export_field_names + self.question_field_names
        ]
        return result

    def get_queryset(self):
        target = self.cleaned_data.get("target")
        queryset = self.event.submitters
        if target == "all":
            return queryset
        return queryset.filter(submissions__state=target).distinct()

    def export_data(self):
        queryset = (
            self.get_queryset()
            .prefetch_related("profiles", "profiles__event")
            .order_by("code")
        )
        fields = ["code"]
        for field_name in self.export_field_names:
            if self.cleaned_data.get(field_name):
                fields.append(field_name)
        questions = [
            q for q in self.questions if self.cleaned_data.get(f"question_{q.pk}")
        ]

        data = []

        for speaker in queryset:
            speaker_data = {"ID": speaker.code}
            for attr in ("name", "email"):
                if attr in fields:
                    speaker_data[str(self.fields[attr].label)] = getattr(speaker, attr)
            if "avatar" in fields:
                speaker_data[str(self.fields["avatar"].label)] = speaker.get_avatar_url(
                    event=self.event
                )
            if "biography" in fields:
                profile = speaker.event_profile(self.event)
                speaker_data[str(self.fields["biography"].label)] = profile.biography
            if "submission_ids" in fields:
                speaker_data[str(self.fields["submission_ids"].label)] = list(
                    speaker.submissions.filter(event=self.event).values_list(
                        "code", flat=True
                    )
                )
            if "submission_titles" in fields:
                speaker_data[str(self.fields["submission_titles"].label)] = list(
                    speaker.submissions.filter(event=self.event).values_list(
                        "title", flat=True
                    )
                )
            for question in questions:
                answer = Answer.objects.filter(
                    question=question, person=speaker
                ).first()
                if answer:
                    speaker_data[str(question.question)] = answer.answer_string
                else:
                    speaker_data[str(question.question)] = None
            data.append(speaker_data)
        if not data:
            return
        if self.cleaned_data.get("export_format") == "csv":
            return self.csv_export(data)
        else:
            return self.json_export(data)

    @property
    def filename(self):
        return f"{self.event.slug}_speakers"

    def csv_export(self, data):
        delimiters = {
            "newline": "\n",
            "comma": ", ",
        }
        delimiter = delimiters[self.cleaned_data.get("data_delimiter")]

        for row in data:
            for key, value in row.items():
                if isinstance(value, list):
                    row[key] = delimiter.join(value)

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        content = output.getvalue()
        return HttpResponse(
            content,
            content_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="{self.filename}.csv"',
                "Access-Control-Allow-Origin": "*",
            },
        )

    def json_export(self, data):
        content = json.dumps(data, cls=I18nJSONEncoder, indent=2)
        return HttpResponse(
            content,
            content_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{self.filename}.json"',
                "Access-Control-Allow-Origin": "*",
            },
        )
