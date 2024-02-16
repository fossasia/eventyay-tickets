import statistics
from collections import defaultdict
from contextlib import suppress

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.forms.models import BaseModelFormSet, modelformset_factory
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import EventPermissionRequired, PermissionRequired
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms.review import (
    DirectionForm,
    ProposalForReviewerForm,
    ReviewAssignImportForm,
    ReviewerForProposalForm,
    ReviewExportForm,
    ReviewForm,
    TagsForm,
)
from pretalx.orga.forms.submission import SubmissionStateChangeForm
from pretalx.orga.views.submission import BaseSubmissionList
from pretalx.person.models import User
from pretalx.submission.forms import QuestionsForm, SubmissionFilterForm
from pretalx.submission.models import Review, Submission, SubmissionStates


class ReviewDashboard(EventPermissionRequired, BaseSubmissionList):
    template_name = "orga/review/dashboard.html"
    permission_required = "orga.view_review_dashboard"
    paginate_by = 100
    max_page_size = 100_000
    usable_states = (
        SubmissionStates.SUBMITTED,
        SubmissionStates.ACCEPTED,
        SubmissionStates.REJECTED,
        SubmissionStates.CONFIRMED,
    )

    def filter_range(self, queryset):
        review_count = self.request.GET.get("review-count") or ","
        if "," not in review_count:
            return queryset
        min_reviews, max_reviews = review_count.split(",", maxsplit=1)
        if min_reviews:
            with suppress(Exception):
                min_reviews = int(min_reviews)
                if min_reviews > 0:
                    queryset = queryset.filter(review_count__gte=min_reviews)
        if max_reviews:
            with suppress(Exception):
                max_reviews = int(max_reviews)
                if max_reviews < self.max_review_count:
                    queryset = queryset.filter(review_count__lte=max_reviews)
        return queryset

    def get_queryset(self):
        aggregate_method = self.request.event.review_settings["aggregate_method"]
        queryset = (
            self._get_base_queryset(for_review=True)
            .filter(state__in=self.usable_states)
            .annotate(
                review_count=Count("reviews", distinct=True),
                review_nonnull_count=Count(
                    "reviews", distinct=True, filter=Q(reviews__score__isnull=False)
                ),
            )
        )
        queryset = self.filter_range(queryset)

        user_reviews = Review.objects.filter(
            user=self.request.user, submission_id=OuterRef("pk")
        ).values("score")

        queryset = (
            queryset.annotate(user_score=Subquery(user_reviews))
            .select_related("track", "submission_type")
            .prefetch_related(
                "speakers",
                "reviews",
                "reviews__user",
                "reviews__scores",
                "tags",
                "answers",
            )
        )

        for submission in queryset:
            if self.can_see_all_reviews:
                submission.current_score = (
                    submission.median_score
                    if aggregate_method == "median"
                    else submission.mean_score
                )
                if (
                    self.independent_categories
                ):  # Assemble medians/means on the fly. Yay.
                    independent_ids = [cat.pk for cat in self.independent_categories]
                    mapping = defaultdict(list)
                    for review in submission.reviews.all():
                        for score in review.scores.all():
                            if score.category_id in independent_ids:
                                mapping[score.category_id].append(score.value)
                    mapping = {
                        key: round(statistics.fmean(value), 1)
                        for key, value in mapping.items()
                    }
                    result = []
                    for category in self.independent_categories:
                        result.append(mapping.get(category.pk))
                    submission.independent_scores = result
                if self.short_questions:
                    answers = {
                        answer.question_id: answer
                        for answer in submission.answers.all()
                    }
                    submission.short_answers = [
                        answers.get(
                            question.id,
                            {"question_id": question.id, "answer_string": ""},
                        )
                        for question in self.short_questions
                    ]
            else:
                reviews = [
                    review
                    for review in submission.reviews.all()
                    if review.user == self.request.user
                ]
                submission.current_score = None
                if reviews:
                    review = reviews[0]
                    submission.current_score = review.score
                    if self.independent_categories:
                        mapping = {s.category_id: s.value for s in review.scores.all()}
                        result = []
                        for category in self.independent_categories:
                            result.append(mapping.get(category.pk))
                        submission.independent_scores = result
                elif self.independent_categories:
                    submission.independent_scores = [
                        None for _ in range(len(self.independent_categories))
                    ]

        return self.sort_queryset(queryset)

    def sort_queryset(self, queryset):
        order_prevalence = {
            "default": ("is_assigned", "state", "current_score", "code"),
            "score": ("current_score", "state", "code"),
            "my_score": ("user_score", "current_score", "state", "code"),
            "count": ("review_nonnull_count", "code"),
        }
        ordering = self.request.GET.get("sort", "default")
        reverse = True
        if ordering.startswith("-"):
            reverse = False
            ordering = ordering[1:]

        order = order_prevalence.get(ordering, order_prevalence["default"])

        def get_order_tuple(obj):
            result = []
            for key in order:
                value = getattr(obj, key)
                if value is None:
                    value = 100 * -int(reverse or -1)
                result.append(value)
            return tuple(result)

        return sorted(
            queryset,
            key=get_order_tuple,
            reverse=reverse,
        )

    @context
    @cached_property
    def can_accept_submissions(self):
        return self.request.event.submissions.filter(
            state=SubmissionStates.SUBMITTED
        ).exists() and self.request.user.has_perm(
            "submission.accept_or_reject_submissions", self.request.event
        )

    @context
    @cached_property
    def can_see_all_reviews(self):
        return self.request.user.has_perm("orga.view_all_reviews", self.request.event)

    @context
    @cached_property
    def max_review_count(self):
        return (
            self.request.event.submissions.all()
            .annotate(review_count=Count("reviews", distinct=True))
            .aggregate(Max("review_count"))
            .get("review_count__max")
        )

    @context
    @cached_property
    def submissions_reviewed(self):
        return Review.objects.filter(
            user=self.request.user, submission__event=self.request.event
        ).values_list("submission_id", flat=True)

    @context
    @cached_property
    def show_submission_types(self):
        return self.request.event.submission_types.all().count() > 1

    @context
    @cached_property
    def short_questions(self):
        from pretalx.submission.models import QuestionVariant

        return self.request.event.questions.filter(
            target="submission",
            variant__in=[
                QuestionVariant.BOOLEAN,
                QuestionVariant.CHOICES,
                QuestionVariant.MULTIPLE,
                QuestionVariant.DATE,
                QuestionVariant.DATETIME,
                QuestionVariant.BOOLEAN,
                QuestionVariant.NUMBER,
            ],
        )

    @context
    @cached_property
    def independent_categories(self):
        return self.request.event.score_categories.all().filter(
            is_independent=True, active=True
        )

    @context
    @cached_property
    def show_tracks(self):
        return (
            self.request.event.feature_flags["use_tracks"]
            and self.request.event.tracks.all().count() > 1
        )

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        missing_reviews = Review.find_missing_reviews(
            self.request.event, self.request.user
        )
        # Do NOT use len() here! It yields a different result.
        result["missing_reviews"] = missing_reviews.count()
        result["next_submission"] = missing_reviews[0] if missing_reviews else None
        result["pagination_sizes"] = [50, 100, 250, 100_000]
        return result

    def get_pending(self, request):
        form = SubmissionStateChangeForm(request.POST)
        if form.is_valid():
            return form.cleaned_data.get("pending")

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        total = {"accept": 0, "reject": 0, "error": 0}
        pending = self.get_pending(request)
        for key, value in request.POST.items():
            if not key.startswith("s-") or value not in ["accept", "reject"]:
                continue
            code = key.strip("s-")
            try:
                submission = request.event.submissions.filter(
                    state=SubmissionStates.SUBMITTED
                ).get(code=code)
            except (Submission.DoesNotExist, ValueError):
                total["error"] += 1
                continue
            if not request.user.has_perm(
                "submission." + value + "_submission", submission
            ):
                total["error"] += 1
                continue
            if pending:
                submission.pending_state = (
                    SubmissionStates.ACCEPTED
                    if value == "accept"
                    else SubmissionStates.REJECTED
                )
                submission.save()
            else:
                getattr(submission, value)(person=request.user)
            total[value] += 1
        if total["accept"] or total["reject"]:
            msg = str(
                _(
                    "Success! {accepted} proposals were accepted, {rejected} proposals were rejected."
                )
            ).format(accepted=total["accept"], rejected=total["reject"])
            if total["error"]:
                msg += " " + str(
                    _("We were unable to change the state of {count} proposals.")
                ).format(count=total["error"])
            messages.success(request, msg)
        else:
            messages.error(
                request,
                str(
                    _("We were unable to change the state of all {count} proposals.")
                ).format(count=total["error"]),
            )
        return super().get(request, *args, **kwargs)


class BulkReview(EventPermissionRequired, TemplateView):
    template_name = "orga/review/bulk.html"
    permission_required = "orga.perform_reviews"
    paginate_by = None

    @context
    @cached_property
    def filter_form(self):
        return SubmissionFilterForm(
            data=self.request.GET,
            event=self.request.event,
            prefix="filter",
        )

    @context
    @cached_property
    def submissions(self):
        submissions = Review.find_reviewable_submissions(
            event=self.request.event, user=self.request.user
        ).prefetch_related("speakers")
        if self.filter_form.is_valid():
            submissions = self.filter_form.filter_queryset(submissions)
        return submissions

    @context
    @cached_property
    def show_tracks(self):
        return (
            self.request.event.feature_flags["use_tracks"]
            and self.request.event.tracks.all().count() > 1
        )

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        missing_reviews = Review.find_missing_reviews(
            self.request.event, self.request.user
        )
        # Do NOT use len() here! It yields a different result.
        result["missing_reviews"] = missing_reviews.count()
        result["next_submission"] = missing_reviews[0] if missing_reviews else None
        return result

    @context
    @cached_property
    def categories(self):
        return (
            self.request.event.score_categories.all()
            .filter(active=True)
            .prefetch_related("limit_tracks", "scores")
        )

    @context
    @cached_property
    def forms(self):
        own_reviews = {
            review.submission_id: review
            for review in self.request.event.reviews.filter(
                user=self.request.user, submission__in=self.submissions
            )
            .select_related("submission")
            .prefetch_related("scores", "scores__category")
        }
        categories = defaultdict(list)
        for category in self.categories:
            for track in category.limit_tracks.all():
                categories[track.pk].append(category)
            else:
                categories[None].append(category)
        return {
            submission.code: ReviewForm(
                event=self.request.event,
                user=self.request.user,
                submission=submission,
                read_only=False,
                instance=own_reviews.get(submission.pk),
                prefix=f"{submission.code}",
                categories=(
                    categories[submission.track_id] if submission.track_id else []
                )
                + categories[None],
                data=(self.request.POST if self.request.method == "POST" else None),
            )
            for submission in self.submissions
        }

    @context
    @cached_property
    def table(self):
        return [
            {
                "submission": submission,
                "form": self.forms[submission.code],
                "score_fields": [
                    self.forms[submission.code].get_score_field(category)
                    for category in self.categories
                ],
            }
            for submission in self.submissions
        ]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        if not all(form.is_valid() for form in self.forms.values()):
            messages.error(request, _("There have been errors with your input."))
            return super().get(request, *args, **kwargs)
        for form in self.forms.values():
            if form.has_changed():
                form.save()
        messages.success(request, _("Your reviews have been saved."))
        return super().get(request, *args, **kwargs)


class ReviewViewMixin:
    @context
    @cached_property
    def submission(self):
        return get_object_or_404(
            self.request.event.submissions.prefetch_related("speakers", "resources"),
            code__iexact=self.kwargs["code"],
        )

    @cached_property
    def object(self):
        review = (
            self.submission.reviews.exclude(user__in=self.submission.speakers.all())
            .filter(user=self.request.user)
            .first()
        )
        return review

    def get_object(self):
        return self.object

    def get_permission_object(self):
        return self.submission

    @context
    @cached_property
    def read_only(self):
        if self.request.user in self.submission.speakers.all():
            return True
        if self.object and self.object.pk:
            return not self.request.user.has_perm(
                "submission.edit_review", self.get_object()
            )
        return not self.request.user.has_perm(
            "submission.review_submission", self.get_object() or self.submission
        )


class ReviewSubmission(ReviewViewMixin, PermissionRequired, CreateOrUpdateView):
    form_class = ReviewForm
    model = Review
    template_name = "orga/submission/review.html"
    permission_required = "submission.view_reviews"
    write_permission_required = "submission.review_submission"

    @context
    @cached_property
    def review_display(self):
        if self.object:
            review = self.object
            return {
                "score": review.display_score,
                "scores": self.get_scores_for_review(review),
                "text": review.text,
                "user": review.user.get_display_name(),
                "answers": [
                    review.answers.filter(question=question).first()
                    for question in self.qform.queryset
                ],
            }

    @context
    @cached_property
    def has_anonymised_review(self):
        return self.request.event.review_phases.filter(
            can_see_speaker_names=False
        ).exists()

    @context
    @cached_property
    def anonymise_review(self):
        return not getattr(
            self.request.event.active_review_phase, "can_see_speaker_names", True
        )

    @context
    def profiles(self):
        return [
            speaker.event_profile(self.request.event)
            for speaker in self.submission.speakers.all()
        ]

    @context
    @cached_property
    def score_categories(self):
        return self.submission.score_categories

    def get_scores_for_review(self, review):
        scores = []
        score_format = self.request.event.review_settings.get(
            "score_format", "words_numbers"
        )
        review_scores = {score.category: score for score in review.scores.all()}
        for category in self.score_categories:
            score = review_scores.get(category)
            if score:
                scores.append(score.format(score_format))
            else:
                scores.append("×")
        return scores

    @context
    def reviews(self):
        return [
            {
                "score": review.display_score,
                "scores": self.get_scores_for_review(review),
                "text": review.text,
                "user": review.user.get_display_name(),
                "answers": [
                    review.answers.filter(question=question).first()
                    for question in self.qform.queryset
                ],
            }
            for review in self.submission.reviews.exclude(
                pk=(self.object.pk if self.object else None)
            ).prefetch_related("scores", "scores__category")
        ]

    @context
    @cached_property
    def qform(self):
        return QuestionsForm(
            target="reviewer",
            event=self.request.event,
            data=(self.request.POST if self.request.method == "POST" else None),
            files=(self.request.FILES if self.request.method == "POST" else None),
            speaker=self.request.user,
            review=self.object,
            readonly=self.read_only,
        )

    @context
    @cached_property
    def tags_form(self):
        if not self.request.event.tags.all().exists():
            return
        return TagsForm(
            event=self.request.event,
            instance=self.submission,
            data=(self.request.POST if self.request.method == "POST" else None),
            read_only=self.read_only,
        )

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result["done"] = self.request.user.reviews.filter(
            submission__event=self.request.event
        ).count()
        result["total_reviews"] = (
            Review.find_missing_reviews(self.request.event, self.request.user).count()
            + result["done"]
        )
        if result["total_reviews"]:
            result["percentage"] = int(result["done"] * 100 / result["total_reviews"])
        return result

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        kwargs["user"] = self.request.user
        kwargs["submission"] = self.submission
        kwargs["read_only"] = self.read_only
        kwargs["categories"] = self.score_categories
        return kwargs

    def form_valid(self, form):
        if not self.qform.is_valid():
            messages.error(self.request, _("There have been errors with your input."))
            return redirect(self.get_success_url())
        if self.tags_form and not self.tags_form.is_valid():
            messages.error(self.request, _("There have been errors with your input."))
            return redirect(self.get_success_url())
        form.save()
        self.qform.review = form.instance
        self.qform.save()
        if self.tags_form:
            self.tags_form.save()
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        action = self.request.POST.get("review_submit") or "save"
        if action == "abstain":
            Review.objects.get_or_create(
                user=self.request.user, submission=self.submission
            )
            return redirect(self.get_success_url())
        if action == "skip_for_now":
            key = f"{self.request.event.slug}_ignored_reviews"
            ignored_submissions = self.request.session.get(key) or []
            ignored_submissions.append(self.submission.pk)
            self.request.session[key] = ignored_submissions
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def get_success_url(self) -> str:
        action = self.request.POST.get("review_submit")
        if action == "save":
            return self.submission.orga_urls.reviews
            # save, skip_for_now, save_and_next

        key = f"{self.request.event.slug}_ignored_reviews"
        ignored_submissions = self.request.session.get(key) or []
        next_submission = Review.find_missing_reviews(
            self.request.event,
            self.request.user,
            ignore=ignored_submissions,
        ).first()
        if not next_submission:
            ignored_submissions = (
                [self.submission.pk] if action == "skip_for_now" else []
            )
            next_submission = Review.find_missing_reviews(
                self.request.event,
                self.request.user,
                ignore=ignored_submissions,
            ).first()
        self.request.session[key] = ignored_submissions
        if next_submission:
            return next_submission.orga_urls.reviews
        messages.success(self.request, _("Nice, you have no proposals left to review!"))
        return self.request.event.orga_urls.reviews


class ReviewSubmissionDelete(EventPermissionRequired, ReviewViewMixin, TemplateView):
    template_name = "orga/submission/review_delete.html"
    permission_required = "orga.remove_review"

    def get_permission_object(self):
        return self.object

    def post(self, request, *args, **kwargs):
        self.object.delete()
        messages.success(request, _("The review has been deleted."))
        return redirect(self.submission.orga_urls.reviews)


class RegenerateDecisionMails(EventPermissionRequired, TemplateView):
    template_name = "orga/review/regenerate_decision_mails.html"
    permission_required = "orga.change_submissions"

    def get_queryset(self):
        return (
            self.request.event.submissions.filter(
                state__in=[SubmissionStates.ACCEPTED, SubmissionStates.REJECTED],
                speakers__isnull=False,
            )
            .prefetch_related("speakers")
            .distinct()
        )

    @context
    @cached_property
    def count(self):
        return sum(len(proposal.speakers.all()) for proposal in self.get_queryset())

    def post(self, request, **kwargs):
        for submission in self.get_queryset():
            submission.send_state_mail()
        messages.success(
            request,
            _("{count} emails were generated and placed in the outbox.").format(
                count=self.count
            ),
        )
        return redirect(self.request.event.orga_urls.reviews)


class ReviewAssignment(EventPermissionRequired, FormView):
    template_name = "orga/review/assignment.html"
    permission_required = "orga.change_settings"
    form_class = DirectionForm

    @cached_property
    def form_type(self):
        direction = self.request.GET.get("direction")
        if not direction or direction not in ("reviewer", "submission"):
            return "reviewer"
        return direction

    def get_form(self):
        return DirectionForm(self.request.GET)

    @context
    @cached_property
    def review_teams(self):
        return self.request.event.teams.filter(is_reviewer=True)

    @context
    @cached_property
    def formset(self):
        proposals = self.request.event.submissions.order_by("title")
        reviewers = (
            User.objects.filter(
                teams__in=self.request.event.teams.filter(is_reviewer=True)
            )
            .order_by("name")
            .distinct()
        )

        if self.form_type == "submission":
            formset_class = modelformset_factory(
                model=Submission,
                form=ReviewerForProposalForm,
                formset=BaseModelFormSet,
                can_delete=False,
                extra=0,
                max_num=0,
            )
            result = formset_class(
                self.request.POST if self.request.method == "POST" else None,
                files=self.request.FILES if self.request.method == "POST" else None,
                queryset=proposals,
                form_kwargs={"reviewers": reviewers},
                prefix="formset",
            )
            return result
        else:
            formset_class = modelformset_factory(
                User,
                form=ProposalForReviewerForm,
                formset=BaseModelFormSet,
                can_delete=False,
                extra=0,
                max_num=0,
            )
            return formset_class(
                self.request.POST if self.request.method == "POST" else None,
                files=self.request.FILES if self.request.method == "POST" else None,
                queryset=reviewers,
                form_kwargs={"proposals": proposals},
                prefix="formset",
            )

    def post(self, request, *args, **kwargs):
        if not self.formset.is_valid():
            return self.get(self.request, *self.args, **self.kwargs)

        for form in self.formset:
            form.save()
        messages.success(request, _("Saved!"))
        return self.get(self.request, *self.args, **self.kwargs)


class ReviewAssignmentImport(EventPermissionRequired, FormView):
    template_name = "orga/review/assignment-import.html"
    permission_required = "orga.change_settings"
    form_class = ReviewAssignImportForm

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["event"] = self.request.event
        return result

    @transaction.atomic
    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("The reviewers were assigned successfully."))
        return redirect(self.request.event.orga_urls.review_assignments)


class ReviewExport(EventPermissionRequired, FormView):
    permission_required = "orga.change_settings"
    template_name = "orga/review/export.html"
    form_class = ReviewExportForm

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["event"] = self.request.event
        result["user"] = self.request.user
        return result

    def form_valid(self, form):
        result = form.export_data()
        if not result:
            messages.success(self.request, _("No data to be exported"))
            return redirect(self.request.path)
        return result
