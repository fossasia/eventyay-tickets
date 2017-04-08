from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ActivityLog(models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='log_entries',
    )
    person = models.ForeignKey(
        to='person.User',
        on_delete=models.PROTECT,
        related_name='log_entries',
        null=True, blank=True,
    )
    content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.PositiveIntegerField(
        db_index=True
    )
    content_object = GenericForeignKey(
        'content_type', 'object_id',
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, db_index=True,
    )
    action_type = models.CharField(
        max_length=200,
    )
    data = models.TextField(
        null=True, blank=True
    )

    class Meta:
        ordering = ('-timestamp', )
