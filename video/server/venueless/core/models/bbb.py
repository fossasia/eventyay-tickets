import uuid

from django.db import models
from django.utils.crypto import get_random_string


class BBBServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    url = models.URLField()
    secret = models.CharField(max_length=300)


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
        to="World", related_name="bbb_calls", on_delete=models.CASCADE,
    )
    invited_members = models.ManyToManyField(to="User", related_name="bbb_invites",)
