from collections import defaultdict

from django.db import models
from django.template.loader import get_template
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import override, ugettext_lazy as _

from pretalx.common.mixins import LogMixin
from pretalx.mail.models import QueuedMail
from pretalx.person.models import User


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
        ordering = ('-published', )
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

        self.notify_speakers()
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

        new_slots = set(talk for talk in self.talks.select_related('submission', 'room').all())
        old_slots = set(talk for talk in self.previous_schedule.talks.select_related('submission', 'room').all())

        new_submissions = set(talk.submission for talk in new_slots)
        old_submissions = set(talk.submission for talk in old_slots)

        new_slot_by_submission = {talk.submission: talk for talk in new_slots}
        old_slot_by_submission = {talk.submission: talk for talk in old_slots}

        result['new_talks'] = list(new_submissions - old_submissions)
        result['canceled_talks'] = list(old_submissions - new_submissions)

        for submission in (new_submissions & old_submissions):
            old_slot = old_slot_by_submission.get(submission)
            new_slot = new_slot_by_submission.get(submission)
            if new_slot.room and not old_slot.room:
                result['new_talks'].append(new_slot)
            elif not new_slot.room and old_slot.room:
                result['canceled_talks'].append(new_slot)
            elif old_slot.start != new_slot.start:
                if new_slot.room:
                    result['moved_talks'].append({
                        'talk': submission,
                        'old_start': old_slot.start,
                        'new_start': new_slot.start,
                        'old_room': old_slot.room.name,
                        'new_room': new_slot.room.name,
                    })

        result['count'] = len(result['new_talks']) + len(result['canceled_talks']) + len(result['moved_talks'])
        return result

    def notify_speakers(self):
        if self.changes['count'] == len(self.changes['canceled_talks']):
            return

        speakers = defaultdict(lambda: {'create': [], 'update': []})
        if self.changes['action'] == 'create':
            speakers = {
                speaker: {'create': self.talks.filter(submission__speakers=speaker), 'update': []}
                for speaker in User.objects.filter(submissions__slots__schedule=self)
            }
        else:
            for new_talk in self.changes['new_talks']:
                for speaker in new_talk.submission.speakers.all():
                    speakers[speaker]['create'].append(new_talk)
            for moved_talk in self.changes['moved_talks']:
                for speaker in moved_talk['talk'].speakers.all():
                    speakers[speaker]['update'].append(moved_talk)
        for speaker in speakers:
            with override(speaker.locale):
                text = get_template('schedule/speaker_notification.txt').render({'speaker': speaker, **speakers[speaker]})
            QueuedMail.objects.create(
                event=self.event,
                to=speaker.email,
                reply_to=self.event.email,
                subject=_('[{event}] New schedule!').format(event=self.event.slug),
                text=text
            )

    def __str__(self) -> str:
        return str(self.version) or _(f'WIP Schedule for {self.event}')
