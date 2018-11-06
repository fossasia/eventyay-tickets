from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Rebuild static files and language files'

    def add_arguments(self, parser):
        parser.add_argument(
            '-c',
            '--clear',
            action='store_true',
            dest='clear',
            help='Clear the existing files using the storage before trying to copy or link the original file.',
        )
        parser.add_argument(
            '-s',
            '--silent',
            action='store_true',
            dest='silent',
            help='Silence most of the build output.',
        )

    def handle(self, *args, **options):
        silent = 0 if options.get('silent') else 1
        call_command('compilemessages', verbosity=silent)
        call_command(
            'collectstatic', verbosity=silent, interactive=False, clear=options['clear']
        )
        call_command('compress', verbosity=silent)
