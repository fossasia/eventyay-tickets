import sys
from contextlib import suppress

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_scopes import scope, scopes_disabled


class Command(BaseCommand):
    help = 'Run a Python REPL scoped to a specific event. Run with --event__slug=eventslug or with --override to access all events.'

    def create_parser(self, *args, **kwargs):
        parser = super().create_parser(*args, **kwargs)
        parser.parse_args = lambda x: parser.parse_known_args(x)[0]
        return parser

    def handle(self, *args, **options):
        flags = self.create_parser(sys.argv[0], sys.argv[1]).parse_known_args(sys.argv[2:])[1]
        if '--override' in flags:
            with scopes_disabled():
                self.stdout.write(self.style.SUCCESS('All scopes are disabled for this shell session – please be careful!'))
                return self.call_command(*args, **options)

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
        if not all(app_name in models for app_name in lookups):
            self.stdout.write(self.style.ERROR(f'Unknown model! Available models: {", ".join(models.keys())}'))
            return

        scope_options = {
            app_name: models[app_name].objects.get(**app_value)
            for app_name, app_value in lookups.items()
        }
        with scope(**scope_options):
            return self.call_command(*args, **options)

    def call_command(self, *args, **options):
        with suppress(ImportError):
            import django_extensions  # noqa
            return call_command('shell_plus', *args, **options)
        return call_command('shell', *args, **options)
