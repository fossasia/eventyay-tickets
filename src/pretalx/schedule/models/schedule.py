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
from pretalx.mail.context import template_context_from_event
from pretalx.person.models import User
from pretalx.submission.models import SubmissionStates


class Schedule(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event', on_delete=models.PROTECT, related_name='schedules'
    )
    version = models.CharField(
        max_length=190, null=True, blank=True, verbose_name=_('version')
    )
    published = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-published',)
        unique_together = (('event', 'version'),)

    class urls(EventUrls):
        public = '{self.event.urls.schedule}v/{self.url_version}/'

    @transaction.atomic
    def freeze(self, name, user=None, notify_speakers=True):
        from pretalx.schedule.models import TalkSlot

        if name in ['wip', 'latest']:
            raise Exception(f'Cannot use reserved name "{name}" for schedule version.')
        if self.version:
            raise Exception(
                f'Cannot freeze schedule version: already versioned as "{self.version}".'
            )
        if not name:
            raise Exception('Cannot create schedule version without a version name.')

        self.version = name
        self.published = now()
        self.save(update_fields=['published', 'version'])
        self.log_action('pretalx.schedule.release', person=user, orga=True)

        wip_schedule = Schedule.objects.create(event=self.event)

        # Set visibility
        self.talks.filter(
            start__isnull=False,
            submission__state=SubmissionStates.CONFIRMED,
            is_visible=False,
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

    @transaction.atomic
    def unfreeze(self, user=None):
        from pretalx.schedule.models import TalkSlot

        if not self.version:
            raise Exception('Cannot unfreeze schedule version: not released yet.')

        # collect all talks, which have been added since this schedule (#72)
        submission_ids = self.talks.all().values_list('submission_id', flat=True)
        talks = self.event.wip_schedule.talks.exclude(
            submission_id__in=submission_ids
        ).union(self.talks.all())

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
            room__isnull=False, start__isnull=False, is_visible=True
        )

    @cached_property
    def slots(self):
        from pretalx.submission.models import Submission

        return Submission.objects.filter(
            id__in=self.scheduled_talks.values_list('submission', flat=True)
        )

    @cached_property
    def previous_schedule(self):
        queryset = self.event.schedules.exclude(pk=self.pk)
        if self.published:
            queryset = queryset.filter(published__lt=self.published)
        return queryset.order_by('-published').first()

    @staticmethod
    def _search_nearest_match(enviroment):
        '''Search for nearest match in other_slots_qs.'''
        slot = enviroment['slot']
        symetric_dif__rooms = enviroment['slots_helper']['symetric_dif__rooms']

        result = None
        rooms = symetric_dif__rooms[:]
        # start with own room
        room = rooms.pop(rooms.index(slot.room.id))
        rooms.insert(0, room)
        rooms = iter(rooms)
        try:
            room = next(rooms)
        except StopIteration:
            room = None
        run = True
        while run:
            result = Schedule._search_nearest_in_room(enviroment, room)
            if not result:
                try:
                    room = next(rooms)
                except StopIteration:
                    run = False
            else:
                run = False

        if result:
            symetric_dif__rooms.remove(slot.room.id)
            symetric_dif__rooms.remove(room)
        return result

    @staticmethod
    def _search_nearest_in_room(enviroment, room):
        '''Search for nearest match in other_slots_qs with defined room.'''
        slot = enviroment['slot']
        other_slots_qs = enviroment['other_slots_qs']
        other_slots_helper = enviroment['other_slots_helper']
        symetric_dif__rooms_start = enviroment['slots_helper']['symetric_dif__rooms_start']
        already_handled = enviroment['slots_helper']['already_handled']

        result = None

        temp_slots = other_slots_qs.filter(
            submission=slot.submission,
            room=room,
            start__in=symetric_dif__rooms_start[room],
        )
        temp_slots_namedtuple = list(temp_slots.values_list(
            'submission',
            'room',
            'start',
            named=True
        ))
        if len(temp_slots_namedtuple) > 0:
            index = 0
            temp_slot_namedtuple = temp_slots_namedtuple[index]
            temp_slot = temp_slots[index]
            if (temp_slot_namedtuple in other_slots_helper):
                symetric_dif__rooms_start[slot.room.id].remove(slot.start)
                symetric_dif__rooms_start[room].remove(temp_slot_namedtuple.start)
                already_handled.append(temp_slot_namedtuple)
                result =  temp_slot
        return result

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

        old_slots_qs = self.previous_schedule.talks.select_related(
            'submission', 'submission__event', 'room'
        ).all().filter(
            room__isnull=False,
            start__isnull=False,
        ).exclude(
            submission__state=SubmissionStates.DELETED,
        ).order_by(
            'submission',
            'room',
            'start',
        )

        new_slots_qs = self.talks.select_related(
            'submission', 'submission__event', 'room'
        ).all().filter(
            room__isnull=False,
            start__isnull=False,
        ).exclude(
            submission__state=SubmissionStates.DELETED,
        ).order_by(
            'submission',
            'room',
            'start',
        )

        # build helper set of talks containing only submission and slot_index
        # with this we can use the set comparing methodes..
        old_slots_helper = set(old_slots_qs.values_list(
            'submission',
            'room',
            'start',
            named=True
        ))
        new_slots_helper = set(new_slots_qs.values_list(
            'submission',
            'room',
            'start',
            named=True
        ))

        slots_helper = {}
        slots_helper['already_handled'] = []
        from operator import attrgetter
        slots_helper['symetric_dif'] = sorted(
            new_slots_helper ^ old_slots_helper,
            key=attrgetter('submission', 'room', 'start',)
        )

        slots_helper['symetric_dif__rooms_start'] = {}
        for slot_helper in slots_helper['symetric_dif']:
            if slot_helper.room not in slots_helper['symetric_dif__rooms_start']:
                slots_helper['symetric_dif__rooms_start'][slot_helper.room] = []
            slots_helper['symetric_dif__rooms_start'][slot_helper.room].append(slot_helper.start)

        slots_helper['symetric_dif__rooms'] = list(slot.room for slot in slots_helper['symetric_dif'])

        from pretalx.schedule.models import TalkSlot
        # handle all possible changes
        for slot_helper in slots_helper['symetric_dif']:
            if slot_helper not in slots_helper['already_handled']:
                # get original database entries
                old_slot = None
                try:
                    old_slot = old_slots_qs.get(
                        submission=slot_helper.submission,
                        start=slot_helper.start,
                        room=slot_helper.room,
                    )
                except TalkSlot.DoesNotExist:
                    pass
                new_slot = None
                try:
                    new_slot = new_slots_qs.get(
                        submission=slot_helper.submission,
                        start=slot_helper.start,
                        room=slot_helper.room,
                    )
                except TalkSlot.DoesNotExist:
                    pass
                # find first element from other set that matches the submission
                if new_slot:
                    old_slot = Schedule._search_nearest_match({
                        'slot': new_slot,
                        'slots_qs': new_slots_qs,
                        'other_slots_qs': old_slots_qs,
                        'other_slots_helper': old_slots_helper,
                        'slots_helper': slots_helper,
                    })
                elif old_slot:
                    new_slot = Schedule._search_nearest_match({
                        'slot': old_slot,
                        'slots_qs': old_slots_qs,
                        'other_slots_qs': new_slots_qs,
                        'other_slots_helper': new_slots_helper,
                        'slots_helper': slots_helper,
                    })
                if old_slot and new_slot:
                    # if we have found both this is a move.
                    slots_helper['already_handled'].append(slot_helper)
                    result['moved_talks'].append(
                        {
                            'submission': new_slot.submission,
                            'old_start': old_slot.start.astimezone(tz),
                            'new_start': new_slot.start.astimezone(tz),
                            'old_room': old_slot.room.name,
                            'new_room': new_slot.room.name,
                            'new_info': new_slot.room.speaker_info,
                        }
                    )
                elif old_slot and not new_slot:
                    slots_helper['already_handled'].append(slot_helper)
                    result['canceled_talks'].append(old_slot)
                elif not old_slot and new_slot:
                    slots_helper['already_handled'].append(slot_helper)
                    result['new_talks'].append(new_slot)
                else:
                    raise Exception('slot not found! - uhh - that should never happen!')
            # else:
            #     pass
            #     # this entry is already handled... so we skip it..

        result['count'] = (
            len(result['new_talks'])
            + len(result['canceled_talks'])
            + len(result['moved_talks'])
        )
        return result

    @cached_property
    def warnings(self):
        warnings = {
            'talk_warnings': [],
            'unscheduled': [],
            'unconfirmed': [],
            'no_track': [],
        }
        for talk in self.talks.all():
            if not talk.start:
                warnings['unscheduled'].append(talk)
            elif talk.warnings:
                warnings['talk_warnings'].append(talk)
            if talk.submission.state != SubmissionStates.CONFIRMED:
                warnings['unconfirmed'].append(talk)
            if talk.submission.event.settings.use_tracks and not talk.submission.track:
                warnings['no_track'].append(talk)
        return warnings

    @cached_property
    def speakers_concerned(self):
        if self.changes['action'] == 'create':
            return {
                speaker: {
                    'create': self.talks.filter(submission__speakers=speaker),
                    'update': [],
                }
                for speaker in User.objects.filter(submissions__slots__schedule=self)
            }

        if self.changes['count'] == len(self.changes['canceled_talks']):
            return []

        speakers = defaultdict(lambda: {'create': [], 'update': []})
        for new_talk in self.changes['new_talks']:
            for speaker in new_talk.submission.speakers.all():
                speakers[speaker]['create'].append(new_talk)
        for moved_talk in self.changes['moved_talks']:
            for speaker in moved_talk['submission'].speakers.all():
                speakers[speaker]['update'].append(moved_talk)
        return speakers

    @cached_property
    def notifications(self):
        tz = pytz.timezone(self.event.timezone)
        mails = []
        for speaker in self.speakers_concerned:
            with override(speaker.locale), tzoverride(tz):
                notifications = get_template(
                    'schedule/speaker_notification.txt'
                ).render({'speaker': speaker, **self.speakers_concerned[speaker]})
            context = template_context_from_event(self.event)
            context['notifications'] = notifications
            mails.append(
                self.event.update_template.to_mail(
                    user=speaker, event=self.event, context=context, commit=False
                )
            )
        return mails

    def notify_speakers(self):
        for notification in self.notifications:
            notification.save()

    @cached_property
    def url_version(self):
        return quote(self.version) if self.version else 'wip'

    @cached_property
    def is_archived(self):
        if not self.version:
            return False

        return self != self.event.current_schedule

    def __str__(self) -> str:
        """Help when debugging."""
        return f'Schedule(event={self.event.slug}, version={self.version})'
