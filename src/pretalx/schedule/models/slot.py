from django.db import models

from pretalx.common.mixins import LogMixin


class TalkSlot(LogMixin, models.Model):
    submission = models.ForeignKey(
        to='submission.Submission',
        on_delete=models.PROTECT,
        related_name='slots',
    )
    room = models.ForeignKey(
        to='schedule.Room',
        on_delete=models.PROTECT,
        related_name='talks',
    )
    schedule = models.ForeignKey(
        to='schedule.Schedule',
        on_delete=models.PROTECT,
        related_name='talks',
    )
    start = models.DateTimeField()
    end = models.DateTimeField()

    @property
    def event(self):
        return self.submission.event

    def copy_to_schedule(self, new_schedule):
        return TalkSlot.objects.create(
            submission=self.submission,
            room=self.room,
            schedule=new_schedule,
            start=self.start,
            end=self.end,
        )
