from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from pretalx.common.urls import EventUrls


class Review(models.Model):
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

    def __str__(self):
        return f'Review(event={self.submission.event.slug}, submission={self.submission.title}, user={self.user.get_display_name}, score={self.score})'

    @classmethod
    def find_missing_reviews(cls, event, user, ignore=None):
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
    def display_score(self):
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

    class Meta:
        ordering = ('position', )

    class urls(EventUrls):
        base = '{self.event.orga_urls.review_settings}phase/{self.pk}/'
        delete = '{base}delete'
        up = '{base}up'
        down = '{base}down'
        activate = '{base}activate'

    def activate(self):
        self.event.review_phases.all().update(is_active=False)
        self.is_active = True
        self.save()
