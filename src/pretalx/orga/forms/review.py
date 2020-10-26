from django import forms
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelMultipleChoiceField

from pretalx.common.forms.widgets import MarkdownWidget
from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.phrases import phrases
from pretalx.orga.forms.widgets import TagWidget
from pretalx.submission.models import Review, Submission


class TagsForm(ReadOnlyFlag, forms.ModelForm):
    def __init__(self, event, **kwargs):
        self.event = event
        super().__init__(**kwargs)
        if not self.event.tags.all().exists():
            self.fields.pop("tags")
        else:
            self.fields["tags"].queryset = self.event.tags.all()
            self.fields["tags"].required = False

    class Meta:
        model = Submission
        fields = [
            "tags",
        ]
        widgets = {
            "tags": TagWidget,
        }
        field_classes = {
            "tags": SafeModelMultipleChoiceField,
        }


class ReviewForm(ReadOnlyFlag, forms.ModelForm):
    def __init__(self, event, user, *args, instance=None, categories=None, **kwargs):
        self.event = event
        self.categories = categories

        super().__init__(*args, instance=instance, **kwargs)
        self.scores = (
            {
                score.category: score.id
                for score in self.instance.scores.all().select_related("category")
            }
            if self.instance.id
            else {}
        )
        for category in categories:
            self.fields[f"score_{category.id}"] = self.build_score_field(
                category,
                read_only=kwargs.get("read_only", False),
                initial=self.scores.get(category),
            )
            self.fields[f"score_{category.id}"].widget.attrs["autocomplete"] = "off"
        self.fields["text"].widget.attrs["rows"] = 2
        self.fields["text"].widget.attrs["placeholder"] = phrases.orga.example_review
        self.fields["text"].required = event.settings.review_text_mandatory
        self.fields["text"].help_text += " " + phrases.base.use_markdown

    def build_score_field(self, category, read_only=False, initial=None):
        choices = [(None, _("No score"))] if not category.required else []
        for score in category.scores.all():
            choices.append((score.id, str(score)))

        return forms.ChoiceField(
            choices=choices,
            required=category.required,
            widget=forms.RadioSelect,
            disabled=read_only,
            initial=initial,
            label=category.name,
        )

    def get_score_fields(self):
        for category in self.categories:
            yield self[f"score_{category.id}"]

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        current_scores = []
        for category in self.categories:
            score_id = self.cleaned_data.get(f"score_{category.id}")
            if score_id:
                current_scores.append(score_id)
        instance.scores.set(current_scores)
        instance.save()
        return instance

    class Meta:
        model = Review
        fields = ("text", "score")
        widgets = {
            "text": MarkdownWidget,
        }
