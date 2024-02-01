from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager
from i18nfield.fields import I18nCharField

from pretalx.common.mixins.models import OrderedModel, PretalxModel
from pretalx.common.urls import EventUrls


class ReviewScoreCategory(PretalxModel):
    event = models.ForeignKey(
        to="event.Event", related_name="score_categories", on_delete=models.CASCADE
    )
    name = I18nCharField()
    weight = models.DecimalField(max_digits=4, decimal_places=1, default=1)
    required = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    limit_tracks = models.ManyToManyField(
        to="submission.Track",
        verbose_name=_("Limit to tracks"),
        blank=True,
        help_text=_("Leave empty to use this category for all tracks."),
    )
    is_independent = models.BooleanField(
        default=False,
        verbose_name=_("Independent score"),
        help_text=_(
            "Independent scores are not part of the total score. Instead they are shown in a separate column in the review dashboard."
        ),
    )

    class urls(EventUrls):
        base = "{self.event.orga_urls.review_settings}category/{self.pk}/"
        delete = "{base}delete"

    @classmethod
    def recalculate_scores(cls, event):
        for review in event.reviews.all():
            review.save(update_score=True)

    def _validate_independence(self):
        if (
            not self.event.score_categories.exclude(pk=self.pk)
            .filter(is_independent=False)
            .exists()
        ):
            raise ValidationError(
                _("You need to keep at least one non-independent score category!")
            )

    def save(self, *args, **kwargs):
        if self.is_independent:
            if self.pk:
                self._validate_independence()
            self.weight = 0
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_independent:
            self._validate_independence()
        return super().delete(*args, **kwargs)


class ReviewScore(PretalxModel):
    category = models.ForeignKey(
        to=ReviewScoreCategory, related_name="scores", on_delete=models.CASCADE
    )
    value = models.DecimalField(max_digits=7, decimal_places=2)
    label = models.CharField(null=True, blank=True, max_length=200)

    objects = ScopedManager(event="category__event")

    def __str__(self):
        return self.format("words_numbers")

    def format(self, fmt):
        if fmt == "words":
            return self.label

        value = self.value
        if int(value) == value:
            value = int(value)

        # we ignore the format if label and value are the same
        if fmt == "numbers" or (self.label and self.label == str(value)):
            return str(value)

        if fmt == "words_numbers":
            return f"{self.label} ({value})"
        # only remaining version is "numbers_words"
        return f"{value} ({self.label})"

    class Meta:
        ordering = ("value",)


class ReviewManager(models.Manager):
    def get_queryset(self):
        from pretalx.submission.models.submission import SubmissionStates

        return (
            super().get_queryset().exclude(submission__state=SubmissionStates.DELETED)
        )


class AllReviewManager(models.Manager):
    pass


class Review(PretalxModel):
    """Reviews model the opinion of reviewers of a.

    :class:`~pretalx.submission.models.submission.Submission`.

    They can, but don't have to, include a score and a text.

    :param text: The review itself. May be empty.
    :param score: This score is calculated from all the related ``scores``
        and their weights. Do not set it directly, use the ``update_score``
        method instead.
    """

    submission = models.ForeignKey(
        to="submission.Submission", related_name="reviews", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        to="person.User", related_name="reviews", on_delete=models.CASCADE
    )
    text = models.TextField(verbose_name=_("What do you think?"), null=True, blank=True)
    score = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Score"), null=True, blank=True
    )
    scores = models.ManyToManyField(to=ReviewScore, related_name="reviews")

    objects = ScopedManager(event="submission__event", _manager_class=ReviewManager)
    all_objects = ScopedManager(
        event="submission__event", _manager_class=AllReviewManager
    )

    class Meta:
        unique_together = (("user", "submission"),)

    def __str__(self):
        return f"Review(event={self.submission.event.slug}, submission={self.submission.title}, user={self.user.get_display_name}, score={self.score})"

    @classmethod
    def find_reviewable_submissions(cls, event, user, ignore=None):
        """Returns all :class:`~pretalx.submission.models.submission.Submission`
        objects this :class:`~pretalx.person.models.user.User` is allowed to review,
        regardless of whether they have already reviewed them.

        Excludes submissions this user has submitted, and takes track
        :class:`~pretalx.event.models.organiser.Team` permissions into account,
        as well as assignments if the current review phase is limited to assigned
        proposals. The result is ordered by review count.

        :type event: :class:`~pretalx.event.models.event.Event`
        :type user: :class:`~pretalx.person.models.user.User`
        :rtype: Queryset of :class:`~pretalx.submission.models.submission.Submission` objects
        """
        from pretalx.submission.models import SubmissionStates

        queryset = (
            event.submissions.filter(state=SubmissionStates.SUBMITTED)
            .exclude(speakers__in=[user])
            .annotate(review_count=models.Count("reviews"))
            .annotate(
                is_assigned=models.Case(
                    models.When(assigned_reviewers__in=[user], then=1), default=0
                ),
            )
        )
        phase = event.active_review_phase
        if phase and phase.proposal_visibility == "assigned":
            queryset = queryset.filter(is_assigned__gte=1)
        else:
            limit_tracks = user.teams.filter(
                models.Q(all_events=True)
                | models.Q(
                    models.Q(all_events=False) & models.Q(limit_events__in=[event])
                ),
                limit_tracks__isnull=False,
                organiser=event.organiser,
            )
            if limit_tracks.exists():
                tracks = set()
                for team in limit_tracks:
                    tracks.update(team.limit_tracks.filter(event=event))
                queryset = queryset.filter(track__in=tracks)
        if ignore:
            queryset = queryset.exclude(pk__in=ignore)
        # This is not randomised, because order_by("review_count", "?") sets all annotated
        # review_count values to 1.
        return queryset.order_by("-is_assigned", "review_count")

    @classmethod
    def find_missing_reviews(cls, event, user, ignore=None):
        """Returns all :class:`~pretalx.submission.models.submission.Submission`
        objects this :class:`~pretalx.person.models.user.User` still has to review
        for the given :class:`~pretalx.event.models.event.Event`. A subset of
        ``find_reviewable_submissions``.

        :type event: :class:`~pretalx.event.models.event.Event`
        :type user: :class:`~pretalx.person.models.user.User`
        :rtype: Queryset of :class:`~pretalx.submission.models.submission.Submission` objects
        """
        return cls.find_reviewable_submissions(event, user, ignore).exclude(
            reviews__user=user
        )

    @classmethod
    def calculate_score(cls, scores):
        if not scores:
            return None
        return sum(score.value * score.category.weight for score in scores)

    @cached_property
    def event(self):
        return self.submission.event

    @cached_property
    def display_score(self) -> str:
        """Helper method to get a display string of the review's score."""
        if self.score is None:
            return "×"
        if int(self.score) == self.score:
            return str(int(self.score))
        return str(self.score)

    def update_score(self):
        scores = (
            self.scores.all()
            .select_related("category")
            .filter(category__in=self.submission.score_categories)
        )
        self.score = self.calculate_score(scores)

    def save(self, *args, update_score=True, **kwargs):
        if self.id and update_score:
            self.update_score()
        return super().save(*args, **kwargs)

    class urls(EventUrls):
        base = "{self.submission.orga_urls.reviews}"
        delete = "{base}delete"


class ReviewPhase(OrderedModel, PretalxModel):
    """ReviewPhases determine reviewer access rights during a (potentially
    open) time frame.

    :param is_active: Is this phase currently active? There can be only one
        active phase per event. Use the ``activate`` method to activate a
        review phase, as it will take care of this limitation.
    :param position: Helper field to deal with relative positioning of review
        phases next to each other.
    """

    event = models.ForeignKey(
        to="event.Event", related_name="review_phases", on_delete=models.CASCADE
    )
    name = models.CharField(verbose_name=_("Name"), max_length=100)
    start = models.DateTimeField(verbose_name=_("Phase start"), null=True, blank=True)
    end = models.DateTimeField(verbose_name=_("Phase end"), null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=False)

    can_review = models.BooleanField(
        verbose_name=_("Reviewers can write and edit reviews"),
        default=True,
    )
    proposal_visibility = models.CharField(
        verbose_name=_("Reviewers may see these proposals"),
        choices=(
            ("all", _("All")),
            ("assigned", _("Only assigned proposals")),
        ),
        max_length=8,
        default="all",
        help_text=_(
            "If you select 'all', reviewers can review all proposals that their teams have access to (so either all, or specific tracks). "
            "In this mode, assigned proposals will be highlighted and will be shown first in the review workflow. "
        ),
    )
    can_see_other_reviews = models.CharField(
        verbose_name=_("Reviewers can see other reviews"),
        max_length=12,
        choices=(
            ("always", _("Always")),
            ("never", _("Never")),
            ("after_review", _("After reviewing the proposal")),
        ),
        default="after_review",
    )
    can_see_speaker_names = models.BooleanField(
        verbose_name=_("Reviewers can see speaker names"),
        default=True,
    )
    can_see_reviewer_names = models.BooleanField(
        verbose_name=_("Reviewers can see the names of other reviewers"),
        default=True,
    )
    can_change_submission_state = models.BooleanField(
        verbose_name=_("Reviewers can accept and reject proposals"),
        default=False,
    )
    can_tag_submissions = models.CharField(
        verbose_name=_("Reviewers can tag proposals"),
        max_length=12,
        choices=(
            ("never", _("Never")),
            ("use_tags", _("Add and remove existing tags")),
            ("create_tags", _("Add, remove and create tags")),
        ),
        default="never",
    )
    speakers_can_change_submissions = models.BooleanField(
        verbose_name=_("Speakers can modify their proposals before acceptance"),
        help_text=_(
            "By default, modification of proposals is locked after the CfP ends, and is re-enabled once the proposal was accepted."
        ),
        default=False,
    )

    class Meta:
        ordering = ("position",)

    class urls(EventUrls):
        base = "{self.event.orga_urls.review_settings}phase/{self.pk}/"
        delete = "{base}delete"
        up = "{base}up"
        down = "{base}down"
        activate = "{base}activate"

    def activate(self) -> None:
        """Activates this review phase and deactivates all others in this
        event."""
        self.event.review_phases.all().update(is_active=False)
        self.is_active = True
        self.save()

    activate.alters_data = True

    @staticmethod
    def get_order_queryset(event):
        return event.review_phases.all()
