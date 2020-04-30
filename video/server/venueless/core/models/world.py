from django.contrib.postgres.fields import JSONField
from django.db import models


class World(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    title = models.CharField(max_length=300)
    about = models.TextField(null=True, blank=True)
    config = JSONField(null=True, blank=True)
    permission_config = JSONField(null=True, blank=True)
    domain = models.CharField(max_length=250, unique=True, null=True, blank=True)
