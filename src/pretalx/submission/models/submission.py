from django.db import models

from pretalx.common.choices import Choices


class SubmissionStates(Choices):
    SUBMITTED = 'submitted'
    REJECTED = 'rejected'
    ACCEPTED = 'accepted'
    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'

    valid_choices = [SUBMITTED, REJECTED, ACCEPTED, CONFIRMED, CANCELLED]


class Submission(models.Model):
    speakers = models.ManyToManyField(
        to='person.User',
        related_name='submissions',
        null=True, blank=True,
    )
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='submissions',
    )
    title = models.CharField(
        max_length=200,
    )
    subtitle = models.CharField(
        max_length=300,
    )
    submission_type = models.ForeignKey(  # Reasonable default must be set in form/view
        to='submission.SubmissionType',
        related_name='submissions',
        on_delete=models.PROTECT,
    )
    state = models.CharField(
        max_length=SubmissionStates.get_max_length(),
        choices=SubmissionStates.get_choices(),
        default=SubmissionStates.SUBMITTED,
    )
    description = models.TextField(
        null=True, blank=True,
    )
    abstract = models.TextField(
        null=True, blank=True,
    )
    notes = models.TextField(
        null=True, blank=True,
        verbose_name='Notes for the organizer',
    )
    duration = models.PositiveIntegerField(
        null=True, blank=True
    )


class SubmissionAttachment:
    pass
