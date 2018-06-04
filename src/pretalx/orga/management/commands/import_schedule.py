import xml.etree.ElementTree as ET
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from pretalx.event.models import Event, Organiser, Team
from pretalx.person.models import User


class Command(BaseCommand):
    help = 'Imports a frab xml export'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str)

    @transaction.atomic
    def handle(self, *args, **options):
        from pretalx.schedule.utils import process_frab
        path = options.get('path')
        tree = ET.parse(path)
        root = tree.getroot()

        event_data = root.find('conference')
        event = Event.objects.filter(slug__iexact=event_data.find('acronym').text).first()
        if not event:
            event = self.create_event(event_data)

        team = event.organiser.teams.filter(
            can_create_events=True, can_change_teams=True, can_change_organiser_settings=True,
            can_change_event_settings=True, can_change_submissions=True,
        ).first()
        if not team:
            team = Team.objects.create(
                name=str(event.name) + ' Organisers', organiser=event.organiser, all_events=True,
                can_create_events=True, can_change_teams=True, can_change_organiser_settings=True,
                can_change_event_settings=True, can_change_submissions=True,
            )
        for user in User.objects.filter(is_administrator=True):
            team.members.add(user)
        team.save()

        self.stdout.write(self.style.SUCCESS(process_frab(root, event)))

    def create_event(self, event_data):
        name = event_data.find('title').text
        organiser = Organiser.objects.create(name=name)
        event = Event(
            name=name, organiser=organiser,
            slug=event_data.find('acronym').text,
            date_from=datetime.strptime(event_data.find('start').text, '%Y-%m-%d').date(),
            date_to=datetime.strptime(event_data.find('end').text, '%Y-%m-%d').date(),
        )
        event.save()
        Team.objects.create(
            name=name + ' Organisers', organiser=organiser, all_events=True,
            can_create_events=True, can_change_teams=True, can_change_organiser_settings=True,
            can_change_event_settings=True, can_change_submissions=True,
        )
        return event
