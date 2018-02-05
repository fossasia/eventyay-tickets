from collections import defaultdict
from contextlib import suppress
from urllib.parse import quote

import pytz
from django.db import models, transaction
from django.template.loader import get_template
from django.utils.functional import cached_property
from django.utils.timezone import now, override as tzoverride
from django.utils.translation import override, ugettext_lazy as _

from pretalx.agenda.tasks import export_schedule_html
from pretalx.common.mixins import LogMixin
from pretalx.common.urls import EventUrls
from pretalx.mail.models import QueuedMail
from pretalx.person.models import User
from pretalx.submission.models import SubmissionStates


class Schedule(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='schedules',
    )
    version = models.CharField(
        max_length=200,
        null=True, blank=True,
        verbose_name=_('version'),
    )
    published = models.DateTimeField(
        null=True, blank=True
    )

    class Meta:
        ordering = ('-published', )
        unique_together = (('event', 'version'), )

    class urls(EventUrls):
        public = '{self.event.urls.schedule}/v/{self.url_version}'

    @transaction.atomic
    def freeze(self, name, user=None, notify_speakers=True):
        from pretalx.schedule.models import TalkSlot
        if name in ['wip', 'latest']:
            raise Exception(f'Cannot use reserved name "{name}" for schedule version.')
        if self.version:
            raise Exception(f'Cannot freeze schedule version: already versioned as "{self.version}".')

        self.version = name
        self.published = now()
        self.save(update_fields=['published', 'version'])
        self.log_action('pretalx.schedule.release', person=user, orga=True)

        wip_schedule = Schedule.objects.create(event=self.event)

        # Set visibility
        self.talks.filter(
            start__isnull=False, submission__state=SubmissionStates.CONFIRMED, is_visible=False
        ).update(is_visible=True)
        self.talks.filter(is_visible=True).exclude(
            start__isnull=False, submission__state=SubmissionStates.CONFIRMED
        ).update(is_visible=False)

        talks = []
        for talk in self.talks.select_related('submission', 'room').all():
            talks.append(talk.copy_to_schedule(wip_schedule, save=False))
        TalkSlot.objects.bulk_create(talks)

        if notify_speakers:
            self.notify_speakers()

        with suppress(AttributeError):
            del wip_schedule.event.wip_schedule
        with suppress(AttributeError):
            del wip_schedule.event.current_schedule

        if self.event.settings.export_html_on_schedule_release:
            export_schedule_html.apply_async(kwargs={'event_id': self.event.id})

        return self, wip_schedule

    def unfreeze(self, user=None):
        from pretalx.schedule.models import TalkSlot
        if not self.version:
            raise Exception('Cannot unfreeze schedule version: not released yet.')

        # collect all talks, which have been added since this schedule (#72)
        submission_ids = self.talks.all().values_list('submission_id', flat=True)
        talks = self.event.wip_schedule.talks \
            .exclude(submission_id__in=submission_ids) \
            .union(self.talks.all())

        wip_schedule = Schedule.objects.create(event=self.event)
        new_talks = []
        for talk in talks:
            new_talks.append(talk.copy_to_schedule(wip_schedule, save=False))
        TalkSlot.objects.bulk_create(new_talks)

        self.event.wip_schedule.talks.all().delete()
        self.event.wip_schedule.delete()

        with suppress(AttributeError):
            del wip_schedule.event.wip_schedule

        return self, wip_schedule

    @cached_property
    def scheduled_talks(self):
        return self.talks.filter(
            room__isnull=False,
            start__isnull=False,
            is_visible=True,
        )

    @cached_property
    def slots(self):
        from pretalx.submission.models import Submission
        return Submission.objects.filter(id__in=self.scheduled_talks.values_list('submission', flat=True))

    @cached_property
    def previous_schedule(self):
        return self.event.schedules.filter(published__lt=self.published).order_by('-published').first()

    @cached_property
    def changes(self):
        tz = pytz.timezone(self.event.timezone)
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

        new_slots = set(
            talk
            for talk in self.talks.select_related('submission', 'submission__event', 'room').all()
            if talk.is_visible and not talk.submission.is_deleted
        )
        old_slots = set(
            talk
            for talk in self.previous_schedule.talks.select_related('submission', 'submission__event', 'room').all()
            if talk.is_visible and not talk.submission.is_deleted
        )

        new_submissions = set(talk.submission for talk in new_slots)
        old_submissions = set(talk.submission for talk in old_slots)

        new_slot_by_submission = {talk.submission: talk for talk in new_slots}
        old_slot_by_submission = {talk.submission: talk for talk in old_slots}

        result['new_talks'] = [new_slot_by_submission.get(s) for s in new_submissions - old_submissions]
        result['canceled_talks'] = [old_slot_by_submission.get(s) for s in old_submissions - new_submissions]

        for submission in (new_submissions & old_submissions):
            old_slot = old_slot_by_submission.get(submission)
            new_slot = new_slot_by_submission.get(submission)
            if new_slot.room and not old_slot.room:
                result['new_talks'].append(new_slot)
            elif not new_slot.room and old_slot.room:
                result['canceled_talks'].append(new_slot)
            elif old_slot.start != new_slot.start or old_slot.room != new_slot.room:
                if new_slot.room:
                    result['moved_talks'].append({
                        'submission': submission,
                        'old_start': old_slot.start.astimezone(tz),
                        'new_start': new_slot.start.astimezone(tz),
                        'old_room': old_slot.room.name,
                        'new_room': new_slot.room.name,
                        'new_info': new_slot.room.speaker_info,
                    })

        result['count'] = len(result['new_talks']) + len(result['canceled_talks']) + len(result['moved_talks'])
        return result

    def notify_speakers(self):
        tz = pytz.timezone(self.event.timezone)
        speakers = defaultdict(lambda: {'create': [], 'update': []})
        if self.changes['action'] == 'create':
            speakers = {
                speaker: {'create': self.talks.filter(submission__speakers=speaker), 'update': []}
                for speaker in User.objects.filter(submissions__slots__schedule=self)
            }
        else:
            if self.changes['count'] == len(self.changes['canceled_talks']):
                return

            for new_talk in self.changes['new_talks']:
                for speaker in new_talk.submission.speakers.all():
                    speakers[speaker]['create'].append(new_talk)
            for moved_talk in self.changes['moved_talks']:
                for speaker in moved_talk['submission'].speakers.all():
                    speakers[speaker]['update'].append(moved_talk)
        for speaker in speakers:
            with override(speaker.locale), tzoverride(tz):
                text = get_template('schedule/speaker_notification.txt').render(
                    {'speaker': speaker, **speakers[speaker]}
                )
            QueuedMail.objects.create(
                event=self.event,
                to=speaker.email,
                reply_to=self.event.email,
                subject=_('[{event}] New schedule!').format(event=self.event.slug),
                text=text
            )

    @property
    def url_version(self):
        return quote(self.version) if self.version else 'wip'

    @property
    def is_archived(self):
        if not self.version:
            return False

        return self != self.event.current_schedule

    def __str__(self) -> str:
        return f'Schedule(event={self.event.slug}, version={self.version})'
