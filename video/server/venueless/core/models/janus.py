import uuid

from django.db import models


class JanusServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    url = models.URLField()
    room_create_key = models.CharField(max_length=300)
    world_exclusive = models.ForeignKey(
        "World", null=True, blank=True, on_delete=models.PROTECT
    )
