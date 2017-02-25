from django.db import models


class SubmissionType(models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='submission_types',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=100,
    )
    default_duration = models.PositiveIntegerField(
        default=30,
        help_text='Default duration in minutes',
    )
    max_duration = models.PositiveIntegerField(
        default=60,
        help_text='Maximum duration in minutes',
    )
