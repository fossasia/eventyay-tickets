from django.core.management.base import BaseCommand
from django_scopes import scope

from pretix.base.models import Event, Organizer, User
from pretix.eventyay_common.tasks import send_event_webhook


class Command(BaseCommand):
    help = 'Enable talk system for an event'

    def add_arguments(self, parser):
        parser.add_argument('event_slug', type=str, help='Event slug')
        parser.add_argument('-o', dest='organizer_slug', type=str, required=True, help='Organizer slug')
        parser.add_argument('-u', dest='user_email', type=str, required=True, help='User email address')

    def handle(self, event_slug: str, organizer_slug: str, user_email: str, *args, **options):

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            self.stderr.write(f'User with email {user_email} does not exist')
            return

        try:
            organizer = Organizer.objects.get(slug=organizer_slug)
        except Organizer.DoesNotExist:
            self.stderr.write(f'Organizer {organizer_slug} does not exist')
            return

        try:
            with scope(organizer=organizer):
                event = Event.objects.get(slug=event_slug, organizer=organizer)
        except Event.DoesNotExist:
            self.stderr.write(f'Event {organizer_slug}/{event_slug} does not exist')
            return

        send_event_webhook(
            user_id=user.id,
            event={
                'organiser_slug': event.organizer.slug,
                'name': event.name.data,
                'slug': event.slug,
                'date_from': str(event.date_from),
                'date_to': str(event.date_to),
                'timezone': str(event.settings.timezone),
                'locale': event.settings.locale,
                'locales': event.settings.locales,
                'is_video_creation': event.is_video_creation,
            },
            action='create',
        )

        self.stdout.write(f'🎉 Talk system enabled for event {organizer_slug}/{event_slug}.')
