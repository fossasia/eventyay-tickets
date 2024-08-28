import json
from contextlib import suppress

from django import forms
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext as _n
from django_scopes.forms import SafeModelMultipleChoiceField

from pretalx.common.forms.widgets import MarkdownWidget
from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.text.phrases import phrases
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
        allow_empty=False,
        **kwargs,
    ):
        self.event = event
        self.user = user
        self.categories = categories
        self.submission = submission
        self.allow_empty = allow_empty

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
        self.fields["text"].widget.attrs["rows"] = 2
        self.fields["text"].widget.attrs["placeholder"] = phrases.orga.example_review
        self.fields["text"].help_text += " " + phrases.base.use_markdown

    def build_score_field(
        self, category, read_only=False, initial=None, hide_optional=False
    ):
        choices = (
            [(None, _("No score"))]
            if (not category.required or self.allow_empty)
            else []
        )
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

    def clean(self):
        # We have to run all validation in the clean method rather than in the
        # clean_* methods, because we want to allow completely empty forms if
        # allow_empty is True, but we still need to validate **all** fields if
        # the form is not empty.

        cleaned_data = super().clean()

        # Early exit if the form is completely empty
        missing_data = [key for key, value in cleaned_data.items() if not value]
        if len(missing_data) == len(self.fields) and self.allow_empty:
            return cleaned_data

        # This validation would normally run in the clean_text method
        if (
            not cleaned_data.get("text")
            and self.event.review_settings["text_mandatory"]
            and not self.allow_empty
        ):
            self.add_error("text", _("Please provide a review text!"))

        # This validation would normally run in the clean_score_category_{pk} method
        for category in self.categories:
            score = cleaned_data.get(f"score_{category.id}")
            if score in ("", None) and category.required and not self.allow_empty:
                self.add_error(
                    f"score_{category.id}", _("Please provide a review score!")
                )
        return cleaned_data

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


class ReviewAssignmentForm(forms.Form):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        self.reviewers = (
            User.objects.filter(teams__in=self.event.teams.filter(is_reviewer=True))
            .order_by("name")
            .distinct()
        ).prefetch_related("assigned_reviews")
        self.submissions = self.event.submissions.order_by("title").prefetch_related(
            "assigned_reviewers"
        )
        super().__init__(*args, **kwargs)


class ReviewerForProposalForm(ReviewAssignmentForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        review_choices = [(reviewer.id, reviewer.name) for reviewer in self.reviewers]
        for submission in self.submissions:
            self.fields[submission.code] = forms.MultipleChoiceField(
                choices=review_choices,
                widget=forms.SelectMultiple(attrs={"class": "select2"}),
                initial=list(
                    submission.assigned_reviewers.values_list("id", flat=True)
                ),
                label=submission.title,
                required=False,
            )

    def save(self, *args, **kwargs):
        for submission in self.submissions:
            submission.assigned_reviewers.set(self.cleaned_data[submission.code])


class ProposalForReviewerForm(ReviewAssignmentForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        submission_choices = [(sub.id, sub.title) for sub in self.submissions]
        for reviewer in self.reviewers:
            self.fields[reviewer.code] = forms.MultipleChoiceField(
                choices=submission_choices,
                widget=forms.SelectMultiple(attrs={"class": "select2"}),
                initial=list(reviewer.assigned_reviews.values_list("id", flat=True)),
                label=reviewer.name,
                required=False,
            )

    def save(self, *args, **kwargs):
        for reviewer in self.reviewers:
            reviewer.assigned_reviews.set(self.cleaned_data[reviewer.code])


class ReviewExportForm(ExportForm):
    data_delimiter = None
    target = forms.ChoiceField(
        required=True,
        label=_n("Proposal", "Proposals", 1),
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
                label=str(_("Score in “{score_category}”")).format(
                    score_category=score_category.name
                ),
            )

    def get_additional_data(self, obj):
        return {
            sc.name: getattr(obj.scores.filter(category=sc).first(), "value", None)
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
            self._submissions_cache = {
                sub.code: sub for sub in self.event.submissions.all()
            }
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
                self._get_user(key): [self._get_submission(val) for val in value]
                for key, value in uploaded_data.items()
            }
        else:
            # keys should be proposals, values should be lists of users
            new_uploaded_data = {
                self._get_submission(key): [self._get_user(val) for val in value]
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
