from contextlib import suppress

from django.core.management import call_command
from django.core.management.base import BaseCommand

from pretalx.common.models.settings import GlobalSettings


class Command(BaseCommand):
    help = "Rebuild static files and language files"

    def add_arguments(self, parser):
        parser.add_argument(
            "-c",
            "--clear",
            action="store_true",
            dest="clear",
            help="Clear the existing files using the storage before trying to copy or link the original file.",
        )
        parser.add_argument(
            "-s",
            "--silent",
            action="store_true",
            dest="silent",
            help="Silence most of the build output.",
        )

    def handle(self, *args, **options):
        silent = 0 if options.get("silent") else 1
        call_command("compilemessages", verbosity=silent)
        call_command(
            "collectstatic", verbosity=silent, interactive=False, clear=options["clear"]
        )
        call_command("compress", verbosity=silent)
        with suppress(
            Exception
        ):  # This fails if we don't have db access, which is fine
            gs = GlobalSettings()
            del gs.settings.update_check_last
            del gs.settings.update_check_result
            del gs.settings.update_check_result_warning
