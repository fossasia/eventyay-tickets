import uuid

from django.db import models
from django.utils.crypto import get_random_string

from venueless.core.models import User, World


def storedfile_name(instance, filename: str) -> str:
    secret = get_random_string(length=12)
    return "{access}/{world}/{id}.{secret}.{ext}".format(
        access="pub" if instance.public else "priv",
        world=instance.world_id,
        secret=secret,
        id=instance.id,
        ext=filename.split(".")[-1],
    )


class StoredFile(models.Model):
    """
    An uploaded file, with an optional expiry date.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    world = models.ForeignKey(World, on_delete=models.PROTECT)
    expires = models.DateTimeField(null=True, blank=True)
    date = models.DateTimeField(null=True, blank=True)
    filename = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    file = models.FileField(null=True, blank=True, upload_to=storedfile_name, max_length=999)
    public = models.BooleanField(default=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)
    source_url = models.CharField(max_length=255, null=True, blank=True)
