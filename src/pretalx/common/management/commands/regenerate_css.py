from django.core.management.base import BaseCommand

from pretalx.common.tasks import regenerate_css
from pretalx.event.models.event import Event, Event_SettingsStore


class Command(BaseCommand):
    help = 'Rebuild static files and language files'

    def add_arguments(self, parser):
        parser.add_argument('--event', type=str)

    def handle(self, *args, **options):
        event = options.get('event')
        if event:
            try:
                event = Event.objects.get(slug__iexact=event)
            except Event.DoesNotExist:
                self.stdout.write(self.style.ERROR('This event does not exist.'))
                return
            regenerate_css.apply_async(args=(event.pk, ))
            self.stdout.write(self.style.SUCCESS(f'[{event.slug}] Event style was successfully regenerated.'))

        else:
            for es in Event_SettingsStore.objects.filter(key='agenda_css_file').order_by('-object__date_from'):
                event = Event.objects.get(pk=es.object_id)
                regenerate_css.apply_async(args=(event.pk, ))
                self.stdout.write(self.style.SUCCESS(f'[{event.slug}] Event style was successfully regenerated.'))
