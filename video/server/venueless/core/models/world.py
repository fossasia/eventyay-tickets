from django.contrib.postgres.fields import JSONField
from django.db import models


def default_permissions():
    return {
        "world.update": ["admin"],
        "world.announce": ["admin"],
        "room.create": ["admin"],
        "room.announce": ["admin"],
        "room.update": ["admin"],
        "room.delete": ["admin"],
        "chat.moderate": ["admin"],
    }


class World(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    title = models.CharField(max_length=300)
    about = models.TextField(null=True, blank=True)
    config = JSONField(null=True, blank=True)
    permission_config = JSONField(null=True, blank=True, default=default_permissions)
    domain = models.CharField(max_length=250, unique=True, null=True, blank=True)
