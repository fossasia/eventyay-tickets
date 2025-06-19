from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.conf import settings


class LogEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='video_control_log_entries')
    object_id = models.JSONField(encoder=DjangoJSONEncoder)
    content_object = GenericForeignKey("content_type", "object_id")
    datetime = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='video_control_log_entries')
    action_type = models.CharField(max_length=255)
    data = models.JSONField(encoder=DjangoJSONEncoder)
