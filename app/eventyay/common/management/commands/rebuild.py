import os
import subprocess
from contextlib import suppress
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.test import override_settings

from eventyay.base.models.settings import GlobalSettings


def build_vue3_frontend_apps():
    """
    Build the Vue3 frontend apps.

    We don't move the build process of "schedule-editor" here, because we want to reduce the
    difference from upstream pretalx.
    """
    frontend_dir = Path(__file__).parent.parent.parent.parent / "frontend"
    env = os.environ.copy()
    env["BASE_URL"] = settings.STATIC_URL
    app_dir = frontend_dir / "global-nav-menu"
    subprocess.check_call(["npm", "ci"], cwd=app_dir)
    subprocess.check_call(["npm", "run", "build"], cwd=app_dir, env=env)


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
        build_vue3_frontend_apps()
        call_command(
            "collectstatic", verbosity=silent, interactive=False, clear=options["clear"]
        )
        with override_settings(VITE_IGNORE=True):
            frontend_dir = (
                Path(__file__).parent.parent.parent.parent / "frontend/schedule-editor/"
            )
            print("--------------------------")
            print(frontend_dir)
            print("--------------------------")
            env = os.environ.copy()
            env["OUT_DIR"] = str(settings.STATIC_ROOT)
            env["BASE_URL"] = settings.STATIC_URL
            if options["npm_install"] or not (frontend_dir / "node_modules").exists():
                subprocess.check_call(["npm", "ci"], cwd=frontend_dir)
            subprocess.check_call(["npm", "run", "build"], cwd=frontend_dir, env=env)

        # We're setting the verbosity to 0 when calling compress on account of https://github.com/django-compressor/django-compressor/issues/881
        call_command("compress", verbosity=0)

        # This fails if we don't have db access, which is fine
        with suppress(Exception):
            gs = GlobalSettings()
            del gs.settings.update_check_last
            del gs.settings.update_check_result
            del gs.settings.update_check_result_warning
