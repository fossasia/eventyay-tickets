from django.db import models
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin


class Schedule(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='schedules',
    )
    version = models.CharField(
        max_length=200,
        null=True, blank=True,
    )
    published = models.DateTimeField(
        null=True, blank=True
    )

    class Meta:
        unique_together = (('event', 'version'), )

    def freeze(self, name, user=None):
        if self.version:
            raise Exception(f'Cannot freeze schedule version: already versioned as "{self.version}".')

        self.version = name
        self.published = now()
        self.save(update_fields=['published', 'version'])
        self.log_action('pretalx.schedule.release', person=user, orga=True)

        wip_schedule = Schedule.objects.create(event=self.event)
        for talk in self.talks.all():
            talk.copy_to_schedule(wip_schedule)
        return self, wip_schedule

    def unfreeze(self, user=None):
        if not self.version:
            raise Exception('Cannot unfreeze schedule version: not released yet.')
        self.event.wip_schedule.talks.all().delete()
        self.event.wip_schedule.delete()
        wip_schedule = Schedule.objects.create(event=self.event)
        for talk in self.talks.all():
            talk.copy_to_schedule(wip_schedule)
        return self, wip_schedule

    @cached_property
    def scheduled_talks(self):
        return self.talks.filter(
            room__isnull=False,
            start__isnull=False,
        )

    def __str__(self) -> str:
        return str(self.version) or _(f'WIP Schedule for {self.event}')
