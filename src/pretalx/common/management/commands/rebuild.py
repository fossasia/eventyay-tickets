import os
import subprocess
from contextlib import suppress
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.test import override_settings

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
        parser.add_argument(
            "--npm-install",
            action="store_true",
            dest="npm_install",
            help="Update npm dependencies before building.",
        )

    def handle(self, *args, **options):
        silent = 0 if options.get("silent") else 1
        call_command("compilemessages", verbosity=silent)
        call_command(
            "collectstatic", verbosity=silent, interactive=False, clear=options["clear"]
        )
        with override_settings(_VITE_IGNORE=True):
            frontend_dir = (
                Path(__file__).parent.parent.parent.parent / "frontend/schedule-editor/"
            )
            env = os.environ.copy()
            env["OUT_DIR"] = str(settings.STATIC_ROOT)
            env["BASE_URL"] = settings.STATIC_URL
            if options["npm_install"] or not (frontend_dir / "node_modules").exists():
                subprocess.check_call(["npm", "ci"], cwd=frontend_dir)
            subprocess.check_call(["npm", "run", "build"], cwd=frontend_dir, env=env)
        call_command("compress", verbosity=silent)

        # This fails if we don't have db access, which is fine
        with suppress(Exception):
            gs = GlobalSettings()
            del gs.settings.update_check_last
            del gs.settings.update_check_result
            del gs.settings.update_check_result_warning
