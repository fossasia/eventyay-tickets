import xml.etree.ElementTree as ET
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from pretalx.event.models import Event
from pretalx.person.models import EventPermission, User


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
            event = Event(
                name=event_data.find('title').text,
                slug=event_data.find('acronym').text,
                date_from=datetime.strptime(event_data.find('start').text, '%Y-%m-%d').date(),
                date_to=datetime.strptime(event_data.find('end').text, '%Y-%m-%d').date(),
            )
            event.save()

        for user in User.objects.filter(is_administrator=True):
            EventPermission.objects.get_or_create(event=event, user=user, is_orga=True)

        self.stdout.write(self.style.SUCCESS(process_frab(root, event)))
