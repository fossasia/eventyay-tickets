import uuid

from django.db import models
from django.utils.crypto import get_random_string


class BBBServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    url = models.URLField()
    secret = models.CharField(max_length=300)
    world_exclusive = models.ForeignKey(
        "World", null=True, blank=True, on_delete=models.PROTECT
    )
    rooms_only = models.BooleanField(default=False)
    cost = models.IntegerField(default=0)

    def __str__(self):
        return self.url


def random_key():
    return get_random_string(24)


class BBBCall(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created = models.DateTimeField(auto_now_add=True)
    server = models.ForeignKey(BBBServer, on_delete=models.CASCADE)
    meeting_id = models.CharField(max_length=300, default=random_key)
    attendee_pw = models.CharField(max_length=300, default=random_key)
    moderator_pw = models.CharField(max_length=300, default=random_key)
    room = models.OneToOneField(
        to="Room", related_name="bbb_call", on_delete=models.CASCADE, null=True
    )
    world = models.ForeignKey(
        to="World",
        related_name="bbb_calls",
        on_delete=models.CASCADE,
    )
    invited_members = models.ManyToManyField(
        to="User",
        related_name="bbb_invites",
    )
    guest_policy = models.CharField(default="ALWAYS_ACCEPT", max_length=50)
    voice_bridge = models.CharField(null=True, blank=True, max_length=5)
