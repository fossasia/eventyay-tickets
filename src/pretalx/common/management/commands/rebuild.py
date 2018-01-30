from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Rebuild static files and language files"

    def add_arguments(self, parser):
        parser.add_argument(
            '-c', '--clear', action='store_true', dest='clear',
            help="Clear the existing files using the storage "
                 "before trying to copy or link the original file.",
        )

    def handle(self, *args, **options):
        call_command('compilemessages', verbosity=1)
        call_command('collectstatic', verbosity=1, interactive=False, clear=options['clear'])
        call_command('compress', verbosity=1)
