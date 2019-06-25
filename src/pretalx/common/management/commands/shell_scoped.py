import argparse
import sys
from contextlib import suppress

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_scopes import scope


class Command(BaseCommand):
    help = 'Rebuild static files and language files'

    def create_parser(self, *args, **kwargs):
        parser = super().create_parser(*args, **kwargs)
        parser.parse_args = lambda x: parser.parse_known_args(x)[0]
        return parser

    def add_arguments(self, parser):
        parser.add_argument('args', nargs=argparse.REMAINDER)

    def handle(self, *args, **options):
        flags = self.create_parser(sys.argv[0], sys.argv[1]).parse_known_args(sys.argv[2:])[1]
        lookups = {}
        for flag in flags:
            lookup, value = flag.lstrip('-').split('=')
            lookup = lookup.split('__', maxsplit=1)
            lookups[lookup[0]] = {lookup[1] if len(lookup) > 1 else 'pk': value}
        models = {
            model_name.split('.')[-1]: model_class
            for app_name, app_content in apps.all_models.items()
            for (model_name, model_class) in app_content.items()
        }
        scope_options = {
            app_name: models[app_name].objects.get(**app_value)
            for app_name, app_value in lookups.items()
        }

        with scope(**scope_options):
            with suppress(ImportError):
                import django_extensions  # noqa
                return call_command('shell_plus', *args, **options)
            return call_command('shell', *args, **options)
