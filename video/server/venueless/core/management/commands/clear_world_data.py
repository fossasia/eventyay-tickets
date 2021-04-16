from django.core.management.base import BaseCommand

from venueless.core.models import World


class Command(BaseCommand):
    help = "Clear all non-config data from a world"

    def add_arguments(self, parser):
        parser.add_argument("world_id", type=str)

    def handle(self, *args, **options):
        w = World.objects.get(id=options["world_id"])
        w.clear_data()
