import xml.etree.ElementTree as ET
from contextlib import suppress
from datetime import datetime, timedelta

from dateutil.parser import parse
from django.core.management.base import BaseCommand
from django.db import transaction

from pretalx.event.models import Event
from pretalx.person.models import EventPermission, SpeakerProfile, User
from pretalx.schedule.models import Room, TalkSlot
from pretalx.submission.models import (
    Submission, SubmissionStates, SubmissionType,
)


class Command(BaseCommand):
    help = 'Imports a frab xml export'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str)

    @transaction.atomic
    def handle(self, *args, **options):
        path = options.get('path')
        tree = ET.parse(path)
        root = tree.getroot()

        event_data = root.find('conference')
        event = Event.objects.filter(slug__iexact=event_data.find('acronym').text).first()
        if not event:
            event = Event(
                name=event_data.find('title').text,
                slug=event_data.find('acronym').text,
                date_from=datetime.strptime(event_data.find('start').text, '%Y-%m-%d').date(),
                date_to=datetime.strptime(event_data.find('end').text, '%Y-%m-%d').date(),
            )
            event.save()
        for user in User.objects.filter(is_superuser=True):
            EventPermission.objects.get_or_create(event=event, user=user, is_orga=True)

        for day in root.findall('day'):
            for rm in day.findall('room'):
                room, _ = Room.objects.get_or_create(event=event, name=rm.attrib['name'])
                for talk in rm.findall('event'):
                    self._create_talk(talk=talk, room=room, event=event)

        schedule_version = root.find('version').text
        event.wip_schedule.freeze(schedule_version, notify_speakers=False)
        event.schedules.get(version=schedule_version).talks.update(is_visible=True)
        self.stdout.write(self.style.SUCCESS(f'Successfully imported "{event.name}" schedule version "{schedule_version}".'))

    def _create_talk(self, *, talk, room, event):
        date = talk.find('date').text
        start = parse(date + ' ' + talk.find('start').text)
        hours, minutes = talk.find('duration').text.split(':')
        duration = timedelta(hours=int(hours), minutes=int(minutes))
        duration_in_minutes = duration.total_seconds() / 60
        try:
            end = parse(date + ' ' + talk.find('end').text)
        except AttributeError:
            end = start + duration
        sub_type = SubmissionType.objects.filter(
            event=event, name=talk.find('type').text, default_duration=duration_in_minutes
        ).first()

        if not sub_type:
            sub_type = SubmissionType.objects.create(
                name=talk.find('type').text or 'default', event=event, default_duration=duration_in_minutes
            )

        optout = False
        with suppress(AttributeError):
            optout = talk.find('recording').find('optout').text == 'true'

        code = None
        if Submission.objects.filter(code__iexact=talk.attrib['id'], event=event).exists() or not Submission.objects.filter(code__iexact=talk.attrib['id']).exists():
            code = talk.attrib['id']
        elif Submission.objects.filter(code__iexact=talk.attrib['guid'][:16], event=event).exists() or not Submission.objects.filter(code__iexact=talk.attrib['guid'][:16]).exists():
            code = talk.attrib['guid'][:16]
        else:
            code = None

        sub, _ = Submission.objects.get_or_create(
            event=event,
            code=code,
            submission_type=sub_type,
        )
        sub.title = talk.find('title').text
        sub.description = talk.find('description').text
        sub.abstract = talk.find('abstract').text
        sub.content_locale = talk.find('language').text or 'en'
        sub.do_not_record = optout
        sub.state = SubmissionStates.CONFIRMED
        sub.save()

        for person in talk.find('persons').findall('person'):
            user = User.objects.filter(nick=person.text[:60]).first()
            if not user:
                user = User(nick=person.text[:60], name=person.text, email=f'{person.text}@localhost')
                user.save()
                SpeakerProfile.objects.create(user=user, event=event)
            sub.speakers.add(user)

        slot, _ = TalkSlot.objects.get_or_create(
            submission=sub,
            schedule=event.wip_schedule,
        )
        slot.room = room
        slot.is_visible = True
        slot.start = start
        slot.end = end
        slot.save()
