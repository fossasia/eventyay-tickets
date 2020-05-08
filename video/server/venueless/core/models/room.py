import uuid

from django.contrib.postgres.fields import JSONField
from django.db import models


def empty_module_config():
    return []


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    world = models.ForeignKey(
        to="core.World", related_name="rooms", on_delete=models.PROTECT
    )
    permission_config = JSONField(null=True, blank=True)
    module_config = JSONField(null=True, default=empty_module_config)
    name = models.CharField(max_length=300)
    description = models.TextField(null=True, blank=True)
    picture = models.FileField(null=True, blank=True)
    sorting_priority = models.IntegerField(default=0)
    import_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ("sorting_priority", "name")
