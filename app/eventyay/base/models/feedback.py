from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy as _n
from django_scopes import ScopedManager

from eventyay.common.text.phrases import phrases

from .mixins import PretalxModel


class Feedback(PretalxModel):
    """Attendee feedback for a session, aimed at one or all of its speakers.

    :param speaker: If unset, the feedback is directed to all speakers of the session.
    """

    talk = models.ForeignKey(
        to='Submission',
        related_name='feedback',
        on_delete=models.PROTECT,
        verbose_name=_n('Session', 'Sessions', 1),
    )
    speaker = models.ForeignKey(
        to='User',
        related_name='feedback',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name=_n('Speaker', 'Speakers', 1),
    )
    rating = models.IntegerField(null=True, blank=True, verbose_name=_('Rating'))
    review = models.TextField(verbose_name=_('Feedback'), help_text=phrases.base.use_markdown)
    
    author = models.ForeignKey(
        to='User',
        related_name='submitted_feedbacks',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Author'),
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name=_('Is public'),
        help_text=_('If disabled, the feedback is anonymous to the speaker and not shown publicly.')
    )
    is_reported = models.BooleanField(
        default=False,
        verbose_name=_('Is reported'),
        help_text=_('Indicates whether this feedback has been reported by a user.')
    )
    report_count = models.IntegerField(
        default=0,
        verbose_name=_('Report count'),
        help_text=_('Number of times this feedback has been reported.')
    )
    status = models.CharField(
        max_length=20,
        default='published',
        choices=(
            ('published', _('Published')),
            ('pending', _('Pending Review')),
            ('hidden', _('Hidden')),
            ('deleted', _('Deleted')),
        ),
        verbose_name=_('Status'),
    )
    parent = models.ForeignKey(
        to='self',
        related_name='replies',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_('Parent feedback'),
    )

    objects = ScopedManager(event='talk__event')

    def __str__(self):
        """Help when debugging."""
        return f'Feedback(event={self.talk.event.slug}, talk={self.talk.title}, rating={self.rating}, status={self.status})'

class FeedbackReaction(PretalxModel):
    feedback = models.ForeignKey(
        to='Feedback',
        related_name='reactions',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        to='User',
        related_name='feedback_reactions',
        on_delete=models.CASCADE,
    )
    is_upvote = models.BooleanField(default=True)

    class Meta:
        unique_together = (('feedback', 'user'),)

    objects = ScopedManager(event='feedback__talk__event')
