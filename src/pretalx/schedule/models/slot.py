from datetime import timedelta

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
            return int((self.end - self.start).total_seconds() / 60)
        return self.submission.get_duration()

    @property
    def export_duration(self):
        duration = timedelta(minutes=self.duration)
        days = duration.days
        hours = duration.total_seconds() // 3600 - days * 24
        minutes = duration.seconds // 60 % 60
        fmt = f'{minutes:02}'
        if hours or days:
            fmt = f'{hours:02}:{fmt}'
            if days:
                fmt = f'{days}:{fmt}'
        else:
            fmt = f'00:{fmt}'
        return fmt

    @property
    def pentabarf_export_duration(self):
        duration = timedelta(minutes=self.duration)
        days = duration.days
        hours = duration.total_seconds() // 3600 - days * 24
        minutes = duration.seconds // 60 % 60
        return f'{hours:02}{minutes:02}00'

    def copy_to_schedule(self, new_schedule, save=True):
        new_slot = TalkSlot(schedule=new_schedule)

        for field in [f for f in self._meta.fields if f.name not in ('id', 'schedule')]:
            setattr(new_slot, field.name, getattr(self, field.name))

        if save:
            new_slot.save()
        return new_slot
