"""This command supersedes the Django-inbuilt runserver command.

It runs the local frontend server, if node is installed and the setting
is set.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.commands.runserver import Command as Parent


class Command(Parent):
    def handle(self, *args, **options):
        if settings.VITE_DEV_MODE:
            # Start the vite server in the background
            from subprocess import Popen

            # run "npm start" in the frontend directory
            frontend_dir = (
                Path(__file__).parent.parent.parent.parent / "frontend/schedule-editor"
            )
            vite_server = Popen(["npm", "start"], cwd=frontend_dir)

        try:
            super().handle(*args, **options)
        finally:
            if settings.VITE_DEV_MODE:
                # Kill the vite server
                vite_server.kill()
