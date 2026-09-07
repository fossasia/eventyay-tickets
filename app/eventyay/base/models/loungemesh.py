import secrets
import uuid

from django.db import models
from django.utils.timezone import now


def default_token():
    return f"lms_{secrets.token_urlsafe(32)}"


class LoungeMeshServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    url = models.URLField(max_length=300)
    api_secret = models.CharField(max_length=300, blank=True)
    jitsi_app_id = models.CharField(max_length=200, blank=True)
    jitsi_app_secret = models.CharField(max_length=300, blank=True)
    cost = models.IntegerField(default=0)
    event_exclusive = models.ForeignKey(
        "Event", null=True, blank=True, on_delete=models.PROTECT
    )
    organizers = models.ManyToManyField(
        "Organizer", blank=True, related_name="loungemesh_servers"
    )
    events = models.ManyToManyField(
        "Event", blank=True, related_name="loungemesh_servers"
    )

    def __str__(self):
        return self.url


class LoungeMeshAccessToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    event = models.ForeignKey(
        "Event", on_delete=models.CASCADE, related_name="loungemesh_tokens"
    )
    room = models.ForeignKey(
        "Room", on_delete=models.CASCADE, related_name="loungemesh_tokens"
    )
    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="loungemesh_tokens",
    )
    token = models.CharField(max_length=128, unique=True, default=default_token)
    moderator = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["token", "expires"]),
        ]

    @property
    def is_valid(self):
        return self.expires > now()
