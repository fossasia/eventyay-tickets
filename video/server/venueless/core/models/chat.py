import uuid

from django.contrib.postgres.fields import JSONField
from django.db import models


class Channel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=300, null=True)
    room = models.OneToOneField(
        to="Room", related_name="channel", on_delete=models.CASCADE, null=True
    )
    world = models.ForeignKey(
        to="World", related_name="channels", on_delete=models.CASCADE,
    )


class ChatEvent(models.Model):
    id = models.BigIntegerField(
        primary_key=True
    )  # Not using auto-increment since it doesn't give a 100% guarantee on monotony
    channel = models.ForeignKey(
        to=Channel, db_index=True, related_name="chat_events", on_delete=models.CASCADE,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=200)
    sender = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chat_events",
    )
    content = JSONField()


class Membership(models.Model):
    channel = models.ForeignKey(
        to=Channel,
        max_length=300,
        db_index=True,
        related_name="members",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chat_channels",
    )
    volatile = models.BooleanField(default=False)

    class Meta:
        unique_together = (("user", "channel"),)
