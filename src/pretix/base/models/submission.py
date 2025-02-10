from django.db import models
from pretix.base.models import Event
from pretix.base.models.base import LoggedModel


class TalkSubmission(LoggedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    speakers = models.JSONField(default=list)
    status = models.CharField(max_length=50)
    
    class Meta:
        ordering = ('name',)

    def __str__(self):
        return f"Submission:{self.name} - Event: ({self.event.name})"
