import uuid
from collections import defaultdict

from django.db import models
from django.db.models import JSONField


class Channel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=300, null=True)
    room = models.OneToOneField(
        to="Room", related_name="channel", on_delete=models.CASCADE, null=True
    )
    world = models.ForeignKey(
        to="World",
        related_name="channels",
        on_delete=models.CASCADE,
    )

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        if self.room:
            self.room.touch()
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        if self.room:
            self.room.touch()
        return r


class ChatEvent(models.Model):
    id = models.BigIntegerField(
        primary_key=True
    )  # Not using auto-increment since it doesn't give a 100% guarantee on monotony
    channel = models.ForeignKey(
        to=Channel,
        db_index=True,
        related_name="chat_events",
        on_delete=models.CASCADE,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    edited = models.DateTimeField(null=True)
    event_type = models.CharField(max_length=200)
    replaces = models.ForeignKey(
        to="ChatEvent", related_name="replaced_by", null=True, on_delete=models.CASCADE
    )
    sender = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chat_events",
    )
    content = JSONField()

    def serialize_public(self):
        reactions = defaultdict(list)
        for reaction in self.reactions.all():
            reactions[reaction.reaction].append(str(reaction.sender_id))
        return {
            "event_id": self.id,
            "channel": str(self.channel_id),
            "sender": str(self.sender_id) if self.sender_id else None,
            "type": "chat.event",
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "content": self.content,
            "edited": self.edited.isoformat() if self.edited else None,
            "replaces": self.replaces_id,
            "reactions": reactions,
        }


class ChatEventReaction(models.Model):
    reaction = models.TextField()
    sender = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="chat_reactions",
    )
    chat_event = models.ForeignKey(
        ChatEvent,
        on_delete=models.CASCADE,
        related_name="reactions",
    )


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
        on_delete=models.CASCADE,
        related_name="chat_channels",
    )
    volatile = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)

    class Meta:
        unique_together = (("user", "channel"),)

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        self.user.touch()
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        self.user.touch()
        return r
