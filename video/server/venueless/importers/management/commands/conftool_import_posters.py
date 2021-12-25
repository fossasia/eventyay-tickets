from django.core.management.base import BaseCommand

from venueless.core.models import World
from venueless.importers.conftool import create_posters_from_conftool


class Command(BaseCommand):
    help = "Run poster import from conftool"

    def add_arguments(self, parser):
        parser.add_argument("world_id", type=str)

    def handle(self, *args, **options):
        world = World.objects.get(id=options["world_id"])
        u = world.config.get("conftool_url")
        p = world.config.get("conftool_password")

        create_posters_from_conftool(world, u, p)
