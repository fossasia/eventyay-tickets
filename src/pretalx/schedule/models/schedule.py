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
            talk.update_visibility()
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

    @cached_property
    def previous_schedule(self):
        return self.event.schedules.filter(published__lt=self.published).order_by('-published').first()

    @cached_property
    def changes(self):
        result = {
            'count': 0,
            'action': 'update',
            'new_talks': [],
            'canceled_talks': [],
            'moved_talks': [],
        }
        if not self.previous_schedule:
            result['action'] = 'create'
            return result

        new_slots = set(talk.submission for talk in self.talks.all())
        old_slots = set(talk.submission for talk in self.previous_schedule.talks.all())

        for submission in (new_slots & old_slots):
            old_slot = self.previous_schedule.talks.get(submission=submission)
            new_slot = self.talks.get(submission=submission)
            if old_slot.start != new_slot.start:
                result['moved_talks'].append({
                    'talk': submission,
                    'old_start': old_slot.start,
                    'new_start': new_slot.start,
                    'old_room': old_slot.room.name,
                    'new_room': new_slot.room.name,
                })

        result['new_talks'] = list(new_slots - old_slots)
        result['canceled_talks'] = list(old_slots - new_slots)
        result['count'] = len(result['new_talks']) + len(result['canceled_talks']) + len(result['moved_talks'])
        return result

    def __str__(self) -> str:
        return str(self.version) or _(f'WIP Schedule for {self.event}')
