from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django_scopes import ScopedManager

from pretalx.common.urls import EventUrls


class Review(models.Model):
    """Reviews model the opinion of reviewers of a :class:`~pretalx.submission.models.submission.Submission`.

    They can, but don't have to, include a score and a text.

    :param text: The review itself. May be empty.
    :param score: The upper and lower bounds of this value are defined in an
        event's settings.
    :param override_vote: If this field is ``True`` or ``False``, it indicates
        that the reviewer has spent one of their override votes to emphasize
        their opinion of the review. It is ``None`` otherwise.
    """
    submission = models.ForeignKey(
        to='submission.Submission', related_name='reviews', on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        to='person.User', related_name='reviews', on_delete=models.CASCADE
    )
    text = models.TextField(verbose_name=_('What do you think?'), null=True, blank=True)
    score = models.IntegerField(verbose_name=_('Score'), null=True, blank=True)
    override_vote = models.BooleanField(default=None, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = ScopedManager(event='submission__event')

    def __str__(self):
        return f'Review(event={self.submission.event.slug}, submission={self.submission.title}, user={self.user.get_display_name}, score={self.score})'

    @classmethod
    def find_missing_reviews(cls, event, user, ignore=None):
        """
        Returns all :class:`~pretalx.submission.models.submission.Submission`
        objects this :class:`~pretalx.person.models.user.User` still has to
        review for the given :class:`~pretalx.event.models.event.Event`.

        Excludes submissions this user has submitted, and takes track
        :class:`~pretalx.event.models.organiser.Team` permissions into account.
        The result is ordered by review count.

        :type event: :class:`~pretalx.event.models.event.Event`
        :type user: :class:`~pretalx.person.models.user.User`
        :rtype: Queryset of :class:`~pretalx.submission.models.submission.Submission` objects
        """
        from pretalx.submission.models import SubmissionStates

        queryset = (
            event.submissions.filter(state=SubmissionStates.SUBMITTED)
            .exclude(reviews__user=user)
            .exclude(speakers__in=[user])
            .annotate(review_count=models.Count('reviews'))
        )
        limit_tracks = user.teams.filter(
            models.Q(all_events=True)
            | models.Q(
                models.Q(all_events=False)
                & models.Q(limit_events__in=[event])
            ),
            limit_tracks__isnull=False,
        )
        if limit_tracks.exists():
            tracks = set()
            for team in limit_tracks:
                tracks.update(team.limit_tracks.filter(event=event))
            queryset = queryset.filter(track__in=tracks)
        if ignore:
            queryset = queryset.exclude(pk__in=[submission.pk for submission in ignore])
        return queryset.order_by('review_count', '?')

    @cached_property
    def event(self):
        return self.submission.event

    @cached_property
    def display_score(self) -> str:
        """Helper method to get a display string of the review's score."""
        if self.override_vote is True:
            return _('Positive override')
        if self.override_vote is False:
            return _('Negative override (Veto)')
        if self.score is None:
            return '×'
        return self.submission.event.settings.get(
            f'review_score_name_{self.score}'
        ) or str(self.score)

    class urls(EventUrls):
        base = '{self.submission.orga_urls.reviews}'
        delete = '{base}{self.pk}/delete'


class ReviewPhase(models.Model):
    """ReviewPhases determine reviewer access rights during a (potentially open) timeframe.

    :param is_active: Is this phase currently active? There can be only one
        active phase per event. Use the ``activate`` method to activate a
        review phase, as it will take care of this limitation.
    :param position: Helper field to deal with relative positioning of review
        phases next to each other.
    """
    event = models.ForeignKey(
        to='event.Event', related_name='review_phases', on_delete=models.CASCADE
    )
    name = models.CharField(verbose_name=_('Name'), max_length=100)
    start = models.DateTimeField(verbose_name=_('Phase start'), null=True, blank=True)
    end = models.DateTimeField(verbose_name=_('Phase end'), null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=False)

    can_review = models.BooleanField(
        verbose_name=_('Reviewers can write and edit reviews'),
        default=True,
    )
    can_see_other_reviews = models.CharField(
        verbose_name=_('Reviewers can see other reviews'),
        max_length=12,
        choices=(('always', _('Always')), ('never', _('Never')), ('after_review', _('After reviewing the submission'))),
        default='after_review',
    )
    can_see_speaker_names = models.BooleanField(
        verbose_name=_('Reviewers can see speaker names'),
        default=True,
    )
    can_change_submission_state = models.BooleanField(
        verbose_name=_('Reviewers can accept and reject submissions'),
        default=False,
    )
    speakers_can_change_submissions = models.BooleanField(
        verbose_name=_('Speakers can modify their submissions before acceptance'),
        help_text=_('By default, modification of submissions is locked after the CfP ends, and is re-enabled once the submission was accepted.'),
        default=False,
    )

    objects = ScopedManager(event='event')

    class Meta:
        ordering = ('position', )

    class urls(EventUrls):
        base = '{self.event.orga_urls.review_settings}phase/{self.pk}/'
        delete = '{base}delete'
        up = '{base}up'
        down = '{base}down'
        activate = '{base}activate'

    def activate(self) -> None:
        """Activates this review phase and deactivates all others in this event."""
        self.event.review_phases.all().update(is_active=False)
        self.is_active = True
        self.save()
