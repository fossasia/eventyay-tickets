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
    override_vote = models.NullBooleanField(default=None, null=True, blank=True)
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
            return 'ø'
        return self.submission.event.settings.get(
            f'review_score_name_{self.score}'
        ) or str(self.score)

    class urls(EventUrls):
        base = '{self.submission.orga_urls.reviews}'
        delete = '{base}/{self.pk}/delete'
