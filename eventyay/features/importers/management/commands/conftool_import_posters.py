from django.core.management.base import BaseCommand

from eventyay.base.models import Event
from eventyay.base.data.importers.conftool import create_posters_from_conftool


class Command(BaseCommand):
    help = "Run poster import from conftool"

    def add_arguments(self, parser):
        parser.add_argument("event_id", type=str)

    def handle(self, *args, **options):
        event = Event.objects.get(id=options["event_id"])
        u = event.config.get("conftool_url")
        p = event.config.get("conftool_password")

        create_posters_from_conftool(event, u, p)
