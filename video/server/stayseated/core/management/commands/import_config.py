import json

from django.core.management.base import BaseCommand

from stayseated.core.utils.config import import_config


class Command(BaseCommand):
    help = "Import a JSON world config"

    def add_arguments(self, parser):
        parser.add_argument("filename", type=str)

    def handle(self, *args, **options):
        with open(options["filename"]) as f:
            world_data = json.load(f)
            import_config(world_data)
