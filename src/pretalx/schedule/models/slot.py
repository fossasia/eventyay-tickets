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
        null=True, blank=True,
    )
    schedule = models.ForeignKey(
        to='schedule.Schedule',
        on_delete=models.PROTECT,
        related_name='talks',
    )
    is_visible = models.BooleanField()
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)

    class Meta:
        unique_together = (('submission', 'schedule'), )

    @property
    def event(self):
        return self.submission.event

    @property
    def duration(self):
        if self.start and self.end:
            return int((self.end - self.start).seconds / 60)
        return self.submission.get_duration()

    def copy_to_schedule(self, new_schedule, save=True):
        new_slot = TalkSlot(schedule=new_schedule)

        for field in [f for f in self._meta.fields if f.name not in ('id', 'schedule')]:
            setattr(new_slot, field.name, getattr(self, field.name))

        if save:
            new_slot.save()
        return new_slot
