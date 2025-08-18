import copy

from django.core.files import File
from django.db import models


class Thumbnail(models.Model):
    source = models.CharField(max_length=255)
    size = models.CharField(max_length=255)
    thumb = models.FileField(upload_to='pub/thumbs/', max_length=255)

    class Meta:
        unique_together = (('source', 'size'),)


def modelcopy(obj: models.Model, **kwargs):
    n = obj.__class__(**kwargs)
    for f in obj._meta.fields:
        val = getattr(obj, f.name)
        if isinstance(val, (models.Model, File)):
            setattr(n, f.name, copy.copy(val))
        else:
            setattr(n, f.name, copy.deepcopy(val))
    return n
