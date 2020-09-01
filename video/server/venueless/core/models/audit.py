from django.contrib.postgres.fields import JSONField
from django.db import models


class AuditLog(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )
    world = models.ForeignKey(
        "World",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    type = models.CharField(max_length=255)
    data = JSONField()

    def serialize_public(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user": self.user.serialize_public(),
            "type": self.type,
            "data": self.data,
        }
