import datetime as dt
import uuid

from django.db import models
from django.utils.timezone import now


class Announcement(models.Model):
    class States(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        ARCHIVED = "archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    world = models.ForeignKey(
        "World", on_delete=models.CASCADE, related_name="announcements"
    )
    text = models.TextField()
    show_until = models.DateTimeField(null=True)
    state = models.CharField(default=States.DRAFT, choices=States.choices, max_length=8)

    timestamp = models.DateTimeField(auto_now_add=True)

    @property
    def is_visible(self):
        return self.state == self.States.ACTIVE and (
            not self.show_until or self.show_until > now()
        )

    @property
    def allowed_states(self):
        states = {self.state}
        if self.state == self.States.ACTIVE:
            states.add(self.States.ARCHIVED)
        elif self.state == self.States.DRAFT:
            states.add(self.States.ACTIVE)
        return states

    def serialize_public(self):
        return {
            "id": str(self.id),
            "text": self.text,
            "show_until": self.show_until.isoformat()
            if isinstance(self.show_until, dt.datetime)
            else self.show_until,
            "state": self.state,
            "is_visible": self.is_visible,
        }
