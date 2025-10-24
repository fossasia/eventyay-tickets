from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.core.management.base import BaseCommand
from django_scopes import scope

from pretix.base.models import Event, Organizer
from pretix.eventyay_common.tasks import create_world


class Command(BaseCommand):
    help = 'Enable video system for an event'

    def add_arguments(self, parser):
        parser.add_argument('organizer_slug', type=str, help='Organizer slug')
        parser.add_argument('event_slug', type=str, help='Event slug')

    def handle(self, organizer_slug, event_slug, *args, **options):

        try:
            organizer = Organizer.objects.get(slug=organizer_slug)
        except Organizer.DoesNotExist:
            self.stderr.write(f"Organizer {organizer_slug} does not exist")
            return

        try:
            with scope(organizer=organizer):
                event = Event.objects.get(slug=event_slug, organizer=organizer)
        except Event.DoesNotExist:
            self.stderr.write(f"Event {organizer_slug}/{event_slug} does not exist")
            return

        # Generate token for video system (admin token)
        iat = datetime.now(timezone.utc)
        exp = iat + timedelta(days=30)
        payload = {
            'exp': exp,
            'iat': iat,
            'uid': 'ADMIN',
            'has_permission': True,
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        create_world(
            is_video_creation=True,
            event_data={
                'id': event.slug,
                'title': event.name.data,
                'timezone': event.settings.timezone,
                'locale': event.settings.locale,
                'has_permission': True,
                'token': token,
            },
        )

        self.stdout.write(f'🎉 Video system enabled for event {organizer_slug}/{event_slug}.')

