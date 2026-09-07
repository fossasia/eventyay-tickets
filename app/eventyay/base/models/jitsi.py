import uuid

from django.db import models


class JitsiServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    url = models.URLField()
    app_id = models.CharField(max_length=200)
    app_secret = models.CharField(max_length=300)
    key_id = models.CharField(max_length=200, blank=True)
    event_exclusive = models.ForeignKey(
        "Event", null=True, blank=True, on_delete=models.PROTECT
    )
    organizers = models.ManyToManyField(
        "Organizer", blank=True, related_name="jitsi_servers"
    )
    events = models.ManyToManyField(
        "Event", blank=True, related_name="jitsi_servers"
    )

    def __str__(self):
        return self.url
