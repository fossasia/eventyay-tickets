import json
from contextlib import suppress
from functools import partial

from django import forms
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelMultipleChoiceField

from pretalx.common.forms.widgets import MarkdownWidget
from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.phrases import phrases
from pretalx.orga.forms.export import ExportForm
from pretalx.person.models import User
from pretalx.submission.models import Question, Review, Submission


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
            "tags": forms.SelectMultiple(attrs={"class": "select2"}),
        }
        field_classes = {
            "tags": SafeModelMultipleChoiceField,
        }


class ReviewForm(ReadOnlyFlag, forms.ModelForm):
    def __init__(
        self,
        event,
        user,
        *args,
        instance=None,
        categories=None,
        submission=None,
        **kwargs,
    ):
        self.event = event
        self.user = user
        self.categories = categories
        self.submission = submission

        super().__init__(*args, instance=instance, **kwargs)

        # We validate existing score/text server-side to allow form-submit to skip/abstain
        self.fields["text"].required = False
        if self.event.review_settings["text_mandatory"]:
            self.fields["text"].widget.attrs["class"] = "hide-optional"

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
                hide_optional=self.event.review_settings["score_mandatory"],
            )
            setattr(
                self,
                f"clean_score_{category.id}",
                partial(self._clean_score_category, category),
            )
        self.fields["text"].widget.attrs["rows"] = 2
        self.fields["text"].widget.attrs["placeholder"] = phrases.orga.example_review
        self.fields["text"].help_text += " " + phrases.base.use_markdown

    def build_score_field(
        self, category, read_only=False, initial=None, hide_optional=False
    ):
        choices = [(None, _("No score"))] if not category.required else []
        for score in category.scores.all():
            choices.append(
                (
                    score.id,
                    score.format(
                        self.event.review_settings.get("score_format", "words_numbers")
                    ),
                )
            )

        field = forms.ChoiceField(
            choices=choices,
            required=False,
            widget=forms.RadioSelect,
            disabled=read_only,
            initial=initial,
            label=category.name,
        )
        field.widget.attrs["autocomplete"] = "off"
        if hide_optional:
            field.widget.attrs["class"] = "hide-optional"
        return field

    def get_score_fields(self):
        for category in self.categories:
            yield self[f"score_{category.id}"]

    def get_score_field(self, category):
        with suppress(KeyError):
            return self[f"score_{category.id}"]

    def clean_text(self):
        text = self.cleaned_data.get("text")
        if not text and self.event.review_settings["text_mandatory"]:
            raise forms.ValidationError(_("Please provide a review text!"))
        return text

    def _clean_score_category(self, category):
        score = self.cleaned_data.get(f"score_{category.id}")
        if score in ("", None) and category.required:
            raise forms.ValidationError(_("Please provide a review score!"))
        return score

    def save(self, *args, **kwargs):
        self.instance.submission = self.submission
        self.instance.user = self.user
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
        fields = ("text",)
        widgets = {
            "text": MarkdownWidget,
        }


class DirectionForm(forms.Form):
    direction = forms.ChoiceField(
        choices=(
            ("reviewer", _("Assign proposals to reviewers")),
            ("submission", _("Assign reviewers to proposals")),
        ),
        required=False,
    )


class ReviewerForProposalForm(forms.ModelForm):
    def __init__(self, *args, reviewers=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_reviewers"].queryset = reviewers
        self.fields["assigned_reviewers"].label = self.instance.title

    def save(self, *args, **kwargs):
        # No calling 'super().save()' here – it would potentially update a submission's code!
        instance = self.instance
        if "assigned_reviewers" in self.changed_data:
            new_code = self.cleaned_data.get("code")
            if instance.code != new_code:
                instance = instance.event.submissions.all().get(code=new_code)
            instance.assigned_reviewers.set(self.cleaned_data["assigned_reviewers"])

    class Meta:
        model = Submission
        fields = ["assigned_reviewers", "code"]
        widgets = {
            "assigned_reviewers": forms.SelectMultiple(attrs={"class": "select2"}),
            "code": forms.HiddenInput(),
        }


class ProposalForReviewerForm(forms.ModelForm):
    def __init__(self, *args, proposals=None, **kwargs):
        super().__init__(*args, **kwargs)
        initial = proposals.filter(assigned_reviewers__in=[self.instance]).values_list(
            "id", flat=True
        )
        self.fields["assigned_reviews"] = forms.MultipleChoiceField(
            choices=((p.id, p.title) for p in proposals),
            widget=forms.SelectMultiple(attrs={"class": "select2"}),
            label=self.instance.name,
            initial=list(initial),
            required=False,
        )

    def save(self, *args, **kwargs):
        # No calling 'super().save()' here – it would potentially update a user's code!
        instance = self.instance
        if "assigned_reviews" in self.changed_data:
            new_code = self.cleaned_data.get("code")
            if instance.code != new_code:
                instance = User.objects.get(code=new_code)
            instance.assigned_reviews.set(self.cleaned_data["assigned_reviews"])

    class Meta:
        model = User
        fields = ["code"]
        widgets = {"code": forms.HiddenInput()}


class ReviewExportForm(ExportForm):
    data_delimiter = None
    target = forms.ChoiceField(
        required=True,
        label=_("Proposal"),
        choices=(
            ("all", _("All proposals")),
            ("accepted", _("accepted")),
            ("confirmed", _("confirmed")),
            ("rejected", _("rejected")),
        ),
        widget=forms.RadioSelect,
    )
    submission_id = forms.BooleanField(
        required=False,
        label=_("Proposal ID"),
        help_text=_(
            "The unique ID of a proposal is used in the proposal URL and in exports"
        ),
    )
    submission_title = forms.BooleanField(
        required=False,
        label=_("Proposal title"),
    )
    user_name = forms.BooleanField(
        required=False,
        label=_("Reviewer name"),
    )
    user_email = forms.BooleanField(
        required=False,
        label=_("Reviewer email"),
    )

    class Meta:
        model = Review
        model_fields = ["score", "text", "created", "updated"]

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["text"].label = _("Text")
        self._build_score_fields()

    @cached_property
    def questions(self):
        return Question.all_objects.filter(
            target="reviewer",
            active=True,
            event=self.event,
        ).prefetch_related("answers", "answers__review", "options")

    @cached_property
    def score_categories(self):
        sc = self.event.score_categories.filter(active=True)
        if len(sc) == 1:
            return []
        return sc

    @cached_property
    def score_field_names(self):
        return [f"score_{sc.pk}" for sc in self.score_categories]

    @cached_property
    def filename(self):
        return f"{self.event.slug}_reviews"

    @cached_property
    def export_field_names(self):
        return (
            [
                "score",
                "text",
            ]
            + self.score_field_names
            + [
                "submission_id",
                "submission_title",
                "created",
                "updated",
                "user_name",
                "user_email",
            ]
        )

    def _build_score_fields(self):
        for score_category in self.score_categories:
            self.fields[f"score_{score_category.pk}"] = forms.BooleanField(
                required=False,
                label=str(_("Score in '{score_category}'")).format(
                    score_category=score_category.name
                ),
            )

    def get_additional_data(self, obj):
        return {
            str(_("Score in '{score_category}'")).format(
                score_category=sc.name
            ): getattr(obj.scores.filter(category=sc).first(), "value", None)
            for sc in self.score_categories
        }

    def get_queryset(self):
        target = self.cleaned_data.get("target")
        queryset = Review.objects.filter(submission__event=self.event)
        if target != "all":
            queryset = queryset.filter(
                submission__in=self.event.submissions.filter(state=target)
            ).distinct()
        # TODO auto-adjust further to available tracks etc
        queryset = queryset.exclude(submission__speakers__in=[self.user]).distinct()
        return queryset.select_related("submission", "user").prefetch_related(
            "answers", "answers__question", "scores", "scores__category"
        )

    def _get_submission_id_value(self, obj):
        return obj.submission.code

    def _get_submission_title_value(self, obj):
        return obj.submission.title

    def _get_user_name_value(self, obj):
        return obj.user.name

    def _get_user_email_value(self, obj):
        return obj.user.email

    def get_answer(self, question, obj):
        return question.answers.filter(review=obj).first()


class ReviewAssignImportForm(DirectionForm):
    import_file = forms.FileField(label=_("file"))
    replace_assignments = forms.ChoiceField(
        label=_("Replace current assignments"),
        choices=((0, _("No")), (1, _("Yes"))),
        help_text=_(
            "Select to remove all current assignments and replace them with the import. Otherwise, the import will be an addition to the current assignments."
        ),
        widget=forms.RadioSelect,
        initial=False,
    )

    def __init__(self, event, **kwargs):
        self.event = event
        self._user_cache = {}
        self._submissions_cache = {}
        super().__init__(**kwargs)
        self.fields["direction"].required = True

    def _get_user(self, text):
        if text in self._user_cache:
            return self._user_cache[text]
        try:
            user = self.event.reviewers.get(Q(email__iexact=text) | Q(code=text))
            self._user_cache[text] = user
            return user
        except Exception:
            raise forms.ValidationError(str(_("Unknown user: {}")).format(text))

    def _get_submission(self, text):
        if not self._submissions_cache:
            self._submissions_cache = {s.code: s for s in self.event.submissions.all()}
        try:
            return self._submissions_cache[text.strip().upper()]
        except Exception:
            raise forms.ValidationError(str(_("Unknown proposal: {}")).format(text))

    def clean_import_file(self):
        uploaded_file = self.cleaned_data["import_file"]
        try:
            data = json.load(uploaded_file)
        except Exception:
            raise forms.ValidationError(_("Cannot parse JSON file."))
        return data

    def clean(self):
        super().clean()
        uploaded_data = self.cleaned_data.get("import_file")
        direction = self.cleaned_data.get("direction")
        if not uploaded_data:
            raise forms.ValidationError(_("Cannot parse JSON file."))
        if direction == "reviewer":
            # keys should be users, values should be lists of proposals
            new_uploaded_data = {
                self._get_user(key): [self._get_submission(v) for v in value]
                for key, value in uploaded_data.items()
            }
        else:
            # keys should be proposals, values should be lists of users
            new_uploaded_data = {
                self._get_submission(key): [self._get_user(v) for v in value]
                for key, value in uploaded_data.items()
            }

        self.cleaned_data["import_file"] = new_uploaded_data
        return self.cleaned_data

    def save(self):
        direction = self.cleaned_data.get("direction")
        replace_assignments = self.cleaned_data.get("replace_assignments")
        uploaded_data = self.cleaned_data.get("import_file")

        if replace_assignments in (1, "1"):
            # There's no .update() for m2m fields
            # We'll just assume that there are less reviewers than proposals, typically,
            # so this should result in less queries
            for user in self.event.reviewers:
                user.assigned_reviews.set([])

        if direction == "reviewer":
            # keys should be users, values should be lists of proposals
            for user, proposals in uploaded_data.items():
                user.assigned_reviews.add(*proposals)
        else:
            for proposal, users in uploaded_data.items():
                proposal.assigned_reviewers.add(*users)
