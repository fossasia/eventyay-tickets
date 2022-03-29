import json
from io import StringIO

from defusedcsv import csv
from django import forms
from django.http import HttpResponse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from i18nfield.utils import I18nJSONEncoder


class ExportForm(forms.Form):
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

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self._build_model_fields()
        self._build_question_fields()

    @property
    def questions(self):
        raise NotImplementedError

    @property
    def filename(self):
        raise NotImplementedError

    @cached_property
    def question_field_names(self):
        return [f"question_{question.pk}" for question in self.questions]

    @cached_property
    def export_fields(self):
        result = [
            forms.BoundField(self, self.fields[field], field)
            for field in self.export_field_names + self.question_field_names
        ]
        return result

    def _build_model_fields(self):
        for field in self.Meta.model_fields:
            self.fields[field] = forms.BooleanField(
                required=False,
                label=self.Meta.model._meta.get_field(field).verbose_name,
            )

    def _build_question_fields(self):
        for question in self.questions:
            self.fields[f"question_{question.pk}"] = forms.BooleanField(
                required=False,
                label=str(_("Answer to the question '{q}'")).format(
                    q=question.question
                ),
            )

    def clean(self):
        data = super().clean()
        if (
            data.get("export_format") == "csv"
            and "data_delimiter" in self.fields
            and not data.get("data_delimiter")
        ):
            self.add_error(
                "data_delimiter",
                forms.ValidationError(
                    _("Please select a delimiter for your CSV export.")
                ),
            )
        return data

    def get_object_attribute(self, obj, attribute):
        method = getattr(self, f"_get_{attribute}_value", None)
        if method:
            return method(obj)
        return getattr(obj, attribute, None)

    def get_data(self, queryset, fields, questions):
        data = []

        for obj in queryset:
            object_data = {}
            code = getattr(obj, "code", None)
            if code:
                object_data["ID"] = code
            prepare_method = getattr(self, "_prepare_object_data", None)
            if prepare_method:
                obj = prepare_method(obj)
            for field in fields:
                object_data[str(self.fields[field].label)] = self.get_object_attribute(
                    obj, field
                )

            for question in questions:
                answer = self.get_answer(question, obj)
                if answer:
                    object_data[str(question.question)] = answer.answer_string
                else:
                    object_data[str(question.question)] = None

            if hasattr(self, "get_additional_data"):
                object_data.update(**self.get_additional_data(obj))
            data.append(object_data)
        return data

    def export_data(self):
        fields = [
            field_name
            for field_name in self.export_field_names
            if self.cleaned_data.get(field_name)
        ]
        questions = [
            q for q in self.questions if self.cleaned_data.get(f"question_{q.pk}")
        ]
        data = self.get_data(self.get_queryset(), fields, questions)
        if not data:
            return
        if self.cleaned_data.get("export_format") == "csv":
            return self.csv_export(data)
        else:
            return self.json_export(data)

    def csv_export(self, data):
        delimiters = {
            "newline": "\n",
            "comma": ", ",
        }
        delimiter = delimiters[self.cleaned_data.get("data_delimiter") or "newline"]

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
