import uuid

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.crypto import get_random_string


def cachedfile_name(instance, filename: str) -> str:
    secret = get_random_string(length=12)
    ext = filename.split(".")[-1]
    return f"cachedfiles/{instance.id}.{secret}.{ext}"


class CachedFile(models.Model):
    """
    An uploaded file, primarily used for API uploads. Deleted after expiry.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    expires = models.DateTimeField()
    timestamp = models.DateTimeField(null=True, blank=True)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=255)
    session_key = models.TextField(
        null=True, blank=True
    )  # only allow processing by the same user / token, if set. If unset, the file cannot be processed further, but can be used for downloads by anybody.
    file = models.FileField(
        null=True, blank=True, upload_to=cachedfile_name, max_length=255
    )

    class Meta:
        indexes = [models.Index(fields=["expires"])]


@receiver(post_delete, sender=CachedFile)
def cached_file_delete(sender, instance, **kwargs):
    if instance.file:
        # Pass false so FileField doesn't save the model.
        instance.file.delete(False)
