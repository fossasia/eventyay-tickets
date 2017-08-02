import xml.etree.ElementTree as ET
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
        event = Event(
            name=event_data.find('title').text,
            slug=event_data.find('acronym').text,
            date_from=datetime.strptime(event_data.find('start').text, '%Y-%m-%d').date(),
            date_to=datetime.strptime(event_data.find('end').text, '%Y-%m-%d').date(),
        )
        event.save()
        for user in User.objects.filter(is_superuser=True):
            EventPermission.objects.create(event=event, user=user, is_orga=True)

        for day in root.findall('day'):
            for rm in day.findall('room'):
                room, _ = Room.objects.get_or_create(event=event, name=rm.attrib['name'])
                for talk in rm.findall('event'):
                    date = talk.find('date').text
                    start = parse(date + ' ' + talk.find('start').text)
                    try:
                        end = parse(date + ' ' + talk.find('end').text)
                    except:
                        hours, minutes = talk.find('duration').text.split(':')
                        duration = timedelta(hours=int(hours), minutes=int(minutes))
                        end = start + duration
                    sub_type = SubmissionType.objects.filter(event=event, name=talk.find('type').text).first()

                    if not sub_type:
                        sub_type = SubmissionType(name=talk.find('type').text or 'default', event=event)
                        sub_type.save()

                    sub = Submission.objects.create(
                        event=event,
                        code=talk.attrib['id'],
                        submission_type=sub_type,
                        title=talk.find('title').text,
                        description=talk.find('description').text,
                        abstract=talk.find('abstract').text,
                        content_locale=talk.find('language').text or 'en',
                        do_not_record=talk.find('recording').find('optout').text == 'true',
                        state=SubmissionStates.CONFIRMED,
                    )
                    for person in talk.find('persons').findall('person'):
                        user = User.objects.filter(nick=person.text).first()
                        if not user:
                            user = User(nick=person.text, name=person.text, email=f'{person.text}@localhost')
                            user.save()
                            SpeakerProfile.objects.create(user=user, event=event)
                        sub.speakers.add(user)

                    TalkSlot.objects.create(
                        submission=sub,
                        schedule=event.wip_schedule,
                        room=room,
                        is_visible=True,
                        start=start,
                        end=end
                    )

        schedule_version = root.find('version').text
        event.wip_schedule.freeze(schedule_version)
        event.schedules.get(version=schedule_version).talks.update(is_visible=True)
