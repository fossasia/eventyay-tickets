from django.db import models
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField

from pretalx.common.mixins import LogMixin
from pretalx.common.urls import EventUrls


def pleasing_number(number):
    if int(number) == number:
        return int(number)
    return number


class SubmissionType(LogMixin, models.Model):
    """Each :class:`~pretalx.submission.models.submission.Submission` has one SubmissionType.

    SubmissionTypes are used to group submissions by default duration (which
    can be overridden on a per-submission basis), and to be able to offer
    different deadlines for some parts of the
    :class:`~pretalx.event.models.event.Event`.
    """
    event = models.ForeignKey(
        to='event.Event', related_name='submission_types', on_delete=models.CASCADE
    )
    name = I18nCharField(max_length=100, verbose_name=_('name'))
    default_duration = models.PositiveIntegerField(
        default=30,
        verbose_name=_('default duration'),
        help_text=_('Default duration in minutes'),
    )
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('deadline'),
        help_text=_('If you want a different deadline than the global deadline for this submission type, enter it here.'),
    )

    class urls(EventUrls):
        base = edit = '{self.event.cfp.urls.types}{self.pk}/'
        default = '{base}default'
        delete = '{base}delete'
        prefilled_cfp = '{self.event.cfp.urls.public}?submission_type={self.slug}'

    def __str__(self) -> str:
        """Used in choice drop downs."""
        if self.default_duration > 60 * 24:
            return _('{name} ({duration} days)').format(
                name=self.name,
                duration=pleasing_number(round(self.default_duration / 60 / 24, 1)),
            )
        if self.default_duration > 90:
            return _('{name} ({duration} hours)').format(
                name=self.name,
                duration=pleasing_number(round(self.default_duration / 60, 1)),
            )
        return _('{name} ({duration} minutes)').format(
            name=self.name, duration=self.default_duration
        )

    @property
    def slug(self) -> str:
        """The slug makes tracks more readable in URLs.

        It consists of the ID, followed by a slugified (and, in lookups,
        optional) form of the submission type name.
        """
        return f'{self.id}-{slugify(self.name)}'

    def update_duration(self):
        """Updates the duration of all :class:`~pretalx.schedule.models.slot.TalkSlot` objects of :class:`~pretalx.submission.models.submission.Submission` objects of this type.

        Runs only for submissions that do not override their default duration.
        Should be called whenever ``duration`` changes."""
        for submission in self.submissions.filter(duration__isnull=True):
            submission.update_duration()
