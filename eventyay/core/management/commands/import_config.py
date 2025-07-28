import json

from django.core.management.base import BaseCommand

from eventyay.core.utils.config import import_config


class Command(BaseCommand):
    help = "Import a JSON event config"

    def add_arguments(self, parser):
        parser.add_argument("filename", type=str)

    def handle(self, *args, **options):
        with open(options["filename"]) as f:
            event_data = json.load(f)
            import_config(event_data)
