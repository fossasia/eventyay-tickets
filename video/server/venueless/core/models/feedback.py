import uuid

from django.db import models


class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    timestamp = models.DateTimeField(auto_now_add=True)
    module = models.CharField(max_length=200)
    world = models.ForeignKey(
        "World",
        related_name="feedback",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    message = models.TextField(null=True, blank=True)
    trace = models.TextField(null=True, blank=True)
