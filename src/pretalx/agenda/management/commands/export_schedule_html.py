import os.path
from shutil import make_archive

from bakery.management.commands.build import Command as BakeryBuildCommand
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import get_callable
from django.utils import translation

from pretalx.event.models import Event


class Command(BakeryBuildCommand):
    help = 'Exports event schedule as a static HTML dump'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('event', type=str)
        parser.add_argument('--zip', action='store_true')

    @classmethod
    def get_output_dir(cls, event):
        return os.path.join(settings.HTMLEXPORT_ROOT, event.slug)

    def handle(self, *args, **options):
        try:
            event = Event.objects.get(slug__iexact=options['event'])
        except Event.DoesNotExist:
            raise CommandError('Could not find event with slug "{}"'.format(options['event']))

        self._exporting_event = event
        translation.activate(event.locale)

        settings.COMPRESS_ENABLED = True
        settings.COMPRESS_OFFLINE = True
        call_command('rebuild')  # collect static files and combine/compress them

        settings.BUILD_DIR = self.get_output_dir(event)

        super().handle(*args, **options)

        if options.get('zip'):
            self.make_zip(event, settings.BUILD_DIR)

    def make_zip(self, event, output_dir):
        destination = output_dir
        make_archive(destination, 'zip', destination, destination)

        with open(destination + '.zip', 'br') as f:
            contentfile = ContentFile(f.read())

        default_storage.save(f'{event.slug}/schedule_{event.slug}.zip', contentfile)

    def build_views(self):
        for view_str in self.view_list:
            view = get_callable(view_str)
            view(_exporting_event=self._exporting_event).build_method()
