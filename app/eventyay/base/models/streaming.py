import uuid

from django.db import models


class StreamingServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    name = models.CharField(max_length=300)
    token_secret = models.CharField(max_length=300)
    url_input = models.CharField(
        max_length=300, default="rtmp://server/app/{name}?token={token}"
    )
    url_output = models.CharField(
        max_length=300, default="https://server/hls/{name}.m3u8"
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)
