from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_scopes import scope

from pretix.base.models import Event, Organizer, User
from pretix.eventyay_common.tasks import create_world
from pretix.eventyay_common.utils import encode_email


class Command(BaseCommand):
    help = 'Enable video system for an event'

    def add_arguments(self, parser):
        parser.add_argument('event_slug', type=str, help='Event slug')
        parser.add_argument('-o', dest='organizer_slug', type=str, required=True, help='Organizer slug')
        parser.add_argument('-u', dest='user_email', type=str, required=True, help='User email address')

    def handle(self, event_slug: str, organizer_slug: str, user_email: str, **options):

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email {user_email} does not exist')

        try:
            organizer = Organizer.objects.get(slug=organizer_slug)
        except Organizer.DoesNotExist:
            raise CommandError(f'Organizer {organizer_slug} does not exist')

        try:
            with scope(organizer=organizer):
                event = Event.objects.get(slug=event_slug, organizer=organizer)
        except Event.DoesNotExist:
            raise CommandError(f'Event {organizer_slug}/{event_slug} does not exist')

        # Generate token for video system (admin token)
        iat = datetime.now(timezone.utc)
        exp = iat + timedelta(days=30)
        payload = {
            'exp': exp,
            'iat': iat,
            'uid': encode_email(user.email),
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

