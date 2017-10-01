import datetime

from django.db import models

from pretalx.common.mixins import LogMixin


class Availability(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='availabilities',
        on_delete=models.CASCADE,
    )
    person = models.ForeignKey(
        to='person.SpeakerProfile',
        related_name='availabilities',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    room = models.ForeignKey(
        to='schedule.Room',
        related_name='availabilities',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    start = models.DateTimeField()
    end = models.DateTimeField()

    def serialize(self):
        zerotime = datetime.time(0, 0)
        return {
            'id': self.id,
            'start': str(self.start),
            'end': str(self.end),
            # make sure all-day availabilities are displayed properly in fullcalendar
            'allDay': (self.start.time() == zerotime and self.end.time() == zerotime)
        }
