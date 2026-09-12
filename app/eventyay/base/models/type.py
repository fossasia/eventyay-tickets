from django.db import models, transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField

from eventyay.common.urls import EventUrls
from eventyay.talk_rules.agenda import is_agenda_visible
from eventyay.talk_rules.event import can_change_event_settings
from eventyay.talk_rules.submission import is_cfp_open, orga_can_change_submissions

from .mixins import OrderedModel, PretalxModel


def pleasing_number(number):
    if int(number) == number:
        return int(number)
    return number


class SubmissionType(OrderedModel, PretalxModel):
    """Each :class:`~pretalx.submission.models.submission.Submission` has one
    SubmissionType.

    SubmissionTypes are used to group submissions by default duration (which
    can be overridden on a per-submission basis), and to be able to offer
    different deadlines for some parts of the
    :class:`~pretalx.event.models.event.Event`.
    """

    event = models.ForeignKey(to='Event', related_name='submission_types', on_delete=models.CASCADE)
    name = I18nCharField(max_length=100, verbose_name=_('name'))
    default_duration = models.PositiveIntegerField(
        default=30,
        verbose_name=_('default duration'),
        help_text=_('Default duration in minutes'),
    )
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Deadline'),
        help_text=_('If you want a different deadline than the global deadline for this session type, enter it here.'),
    )
    requires_access_code = models.BooleanField(
        verbose_name=_('Requires access code'),
        help_text=_('This session type will only be shown to submitters with a matching access code.'),
        default=False,
    )
    position = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('position'),
        help_text=_('The position field is used to determine the order that session types are displayed in (lowest first).'),
    )

    log_prefix = 'eventyay.submission_type'

    class Meta:
        ordering = ['position', 'default_duration']
        rules_permissions = {
            'list': is_cfp_open | is_agenda_visible | orga_can_change_submissions,
            'view': is_cfp_open | is_agenda_visible | orga_can_change_submissions,
            'orga_list': orga_can_change_submissions,
            'orga_view': orga_can_change_submissions,
            'create': can_change_event_settings,
            'update': can_change_event_settings,
            'delete': can_change_event_settings,
        }

    class urls(EventUrls):
        """URL patterns for submission type views."""
        base = edit = '{self.event.cfp.urls.types}{self.pk}/'
        default = '{base}default/'
        delete = '{base}delete/'
        prefilled_cfp = '{self.event.cfp.urls.public}?submission_type={self.slug}'

    def __str__(self) -> str:
        """Used in choice drop downs."""
        if not self.default_duration:
            return str(self.name)
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
        return _('{name} ({duration} minutes)').format(name=self.name, duration=self.default_duration)

    @property
    def log_parent(self):
        return self.event

    @property
    def slug(self) -> str:
        """The slug makes tracks more readable in URLs.

        It consists of the ID, followed by a slugified (and, in lookups,
        optional) form of the submission type name.
        """
        return f'{self.id}-{slugify(self.name)}'

    def update_duration(self):
        """Updates the duration of all.

        :class:`~pretalx.schedule.models.slot.TalkSlot` objects of
        :class:`~pretalx.submission.models.submission.Submission` objects of
        this type.

        Runs only for submissions that do not override their default
        duration. Should be called whenever ``duration`` changes.
        """
        for submission in self.submissions.filter(duration__isnull=True):
            submission.update_duration()

    update_duration.alters_data = True

    def save(self, *args, **kwargs):
        """Auto-assign position for new instances."""
        if self.position is None and self.event_id:
            # Get the max position for this event, default to 0 if no types exist
            max_position = self.event.submission_types.aggregate(
                models.Max('position')
            )['position__max']
            self.position = (max_position or 0) + 1
        super().save(*args, **kwargs)

    @staticmethod
    def get_order_queryset(event):
        """Return the queryset used for ordering."""
        return event.submission_types.all()


@receiver(post_save, sender=SubmissionType)
@receiver(post_delete, sender=SubmissionType)
def invalidate_submission_type_catalog_cache(sender, instance, **kwargs):
    from eventyay.base.services.stale_cache import invalidate_catalog_cache

    event_id = instance.event_id
    transaction.on_commit(lambda: invalidate_catalog_cache(event_id, 'submission-types'))
