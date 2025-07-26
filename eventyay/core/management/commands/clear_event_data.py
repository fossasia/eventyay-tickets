from django.core.management.base import BaseCommand
from eventyay.base.models import Event

class Command(BaseCommand):
    help = "Clear all non-config data from an event"

    def add_arguments(self, parser):
        parser.add_argument("event_id", type=str)

    def handle(self, *args, **options):
        e = Event.objects.get(id=options["event_id"])
        e.clear_data()
