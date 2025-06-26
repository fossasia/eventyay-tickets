import logging
import os
import sys
import tempfile

from django.core.management.commands import shell
from django.db import connection
from django_scopes import scope, scopes_disabled

from pretalx.event.models import Event


class Command(shell.Command):  # pragma: no cover

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--print-sql",
            action="store_true",
            help="Print all SQL queries.",
        )
        parser.add_argument(
            "--unsafe-disable-scopes",
            action="store_true",
            help="Don’t use scoping, access data for all events.",
        )
        parser.add_argument("--event", help="Event (slug) to scope all queries to.")

    def get_auto_imports(self):
        return super().get_auto_imports() + [
            "django.conf.settings",
            "django.utils.timezone.now",
        ]

    def handle(self, *args, **options):
        if options.pop("print_sql", None):
            connection.force_debug_cursor = True
            logger = logging.getLogger("django.db.backends")
            logger.setLevel(logging.DEBUG)
            # Further configuration for logger handler can be added here if needed
            # For example, to ensure output goes to stdout/stderr:
            if not logger.handlers:
                handler = logging.StreamHandler()
                logger.addHandler(handler)

        if options.pop("unsafe_disable_scopes", None):
            with scopes_disabled():
                return super().handle(*args, **options)

        event_slug_str = options.pop("event", None)
        if not event_slug_str:
            self.stdout.write(
                self.style.ERROR(
                    "Call this command with an --event or disable scoping with --unsafe-disable-scopes!"
                )
            )
            sys.exit(-1)

        event = Event.objects.filter(slug__iexact=event_slug_str.strip()).first()
        if not event:
            self.stdout.write(self.style.ERROR("Event not found!"))
            sys.exit(-1)

        if options["no_startup"] or os.environ.get("PYTHONSTARTUP"):
            # The user wants to skip startup execution or has their own startup file
            with scope(event=event):
                return super().handle(*args, **options)

        # We’re setting the local event variable to the scoped event in a namedtempfile
        # and are setting that to os.environ
        runline = f"event = Event.objects.get(slug='{event.slug}')"
        startup_file_name = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w+", suffix=".py", delete=False
            ) as f:
                startup_file_name = f.name
                f.write(runline)
            os.environ["PYTHONSTARTUP"] = startup_file_name
            self.stdout.write(
                self.style.SUCCESS(
                    f'Your shell is scoped to the event {event.name}. Use the "event" variable to access it.'
                )
            )

            with scope(event=event):
                return super().handle(*args, **options)
        finally:
            if "PYTHONSTARTUP" in os.environ:
                del os.environ["PYTHONSTARTUP"]

            if startup_file_name and os.path.exists(startup_file_name):
                os.unlink(startup_file_name)

    def ipython(self, options):
        from IPython import start_ipython
        from traitlets.config import Config

        config = Config()
        config.TerminalIPythonApp.display_banner = False
        config.TerminalInteractiveShell.enable_tip = False
        start_ipython(argv=[], user_ns=self.get_namespace(**options), config=config)
