import os.path
from shutil import make_archive

from bakery.management.commands.build import Command as BakeryBuildCommand
from django.conf import settings
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import get_callable
from django.utils import translation
from django.utils.timezone import override as override_timezone

from pretalx.event.models import Event


class Command(BakeryBuildCommand):
    help = 'Exports event schedule as a static HTML dump'

    def __init__(self, *args, **kwargs):
        self._exporting_event = None
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('event', type=str)
        parser.add_argument('--zip', action='store_true')

    @classmethod
    def get_output_dir(cls, event):
        return os.path.join(
            settings.HTMLEXPORT_ROOT, event.slug
        )  # Do not change, this is used to build the correct zip path

    @classmethod
    def get_output_zip_path(cls, event):
        return cls.get_output_dir(event) + '.zip'

    def build_media(self):
        output_dir = self.get_output_dir(self._exporting_event)
        os.makedirs(
            os.path.join(output_dir, 'media', self._exporting_event.slug), exist_ok=True
        )
        return super().build_media()

    def handle(self, *args, **options):
        event_slug = options.get('event')
        try:
            event = Event.objects.get(slug__iexact=event_slug)
        except Event.DoesNotExist:
            raise CommandError(f'Could not find event with slug "{event_slug}".')

        self._exporting_event = event
        translation.activate(event.locale)

        output_dir = self.get_output_dir(event)
        with override_settings(
            COMPRESS_ENABLED=True,
            COMPRESS_OFFLINE=True,
            BUILD_DIR=output_dir,
            MEDIA_URL=os.path.join(settings.MEDIA_URL, event_slug),
            MEDIA_ROOT=os.path.join(settings.MEDIA_ROOT, event_slug),
        ):
            with override_timezone(event.timezone):
                super().handle(*args, **options)
                if options.get('zip', False):
                    make_archive(
                        base_name=output_dir,
                        format='zip',
                        root_dir=settings.HTMLEXPORT_ROOT,
                        base_dir=event.slug,
                    )
                    output_dir += '.zip'
        self.stdout.write(output_dir)

    def build_views(self):
        for view_str in self.view_list:
            view = get_callable(view_str)
            view(_exporting_event=self._exporting_event).build_method()
