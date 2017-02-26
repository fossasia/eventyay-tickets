from django.db import models
from django.utils.crypto import get_random_string

from pretalx.common.choices import Choices


class SubmissionStates(Choices):
    SUBMITTED = 'submitted'
    REJECTED = 'rejected'
    ACCEPTED = 'accepted'
    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'

    valid_choices = [SUBMITTED, REJECTED, ACCEPTED, CONFIRMED, CANCELLED]


class Submission(models.Model):
    code = models.CharField(
        max_length=16,
        db_index=True
    )
    speakers = models.ManyToManyField(
        to='person.User',
        related_name='submissions',
        blank=True,
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

    def assign_code(self):
        # This omits some character pairs completely because they are hard to read even on screens (1/I and O/0)
        # and includes only one of two characters for some pairs because they are sometimes hard to distinguish in
        # handwriting (2/Z, 4/A, 5/S, 6/G).
        charset = list('ABCDEFGHJKLMNPQRSTUVWXYZ3789')
        while True:
            code = get_random_string(length=6, allowed_chars=charset)
            if not Submission.objects.filter(code=code).exists():
                self.code = code
                return

    def save(self, *args, **kwargs):
        if not self.code:
            self.assign_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class SubmissionAttachment:
    pass
