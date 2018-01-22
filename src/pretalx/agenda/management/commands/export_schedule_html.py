import os.path
from shutil import make_archive

from bakery.management.commands.build import Command as BakeryBuildCommand
from django.conf import settings
from django.core.management.base import CommandError
from django.test import override_settings
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

    @classmethod
    def get_output_zip_path(cls, event):
        return cls.get_output_dir(event) + '.zip'

    def handle(self, *args, **options):
        try:
            event = Event.objects.get(slug__iexact=options['event'])
        except Event.DoesNotExist:
            raise CommandError('Could not find event with slug "{}"'.format(options['event']))

        self._exporting_event = event
        translation.activate(event.locale)

        with override_settings(COMPRESS_ENABLED=True, COMPRESS_OFFLINE=True, BUILD_DIR=self.get_output_dir(event)):
            super().handle(*args, **options)
            if options.get('zip'):
                make_archive(settings.BUILD_DIR, 'zip', settings.BUILD_DIR, settings.BUILD_DIR)

    def build_views(self):
        for view_str in self.view_list:
            view = get_callable(view_str)
            view(_exporting_event=self._exporting_event).build_method()
