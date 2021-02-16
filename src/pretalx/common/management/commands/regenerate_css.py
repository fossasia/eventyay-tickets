from django.core.management.base import BaseCommand

from pretalx.common.tasks import regenerate_css
from pretalx.event.models.event import Event


class Command(BaseCommand):
    help = "Rebuild static files and language files"

    def add_arguments(self, parser):
        parser.add_argument("--event", type=str)
        parser.add_argument(
            "-s",
            "--silent",
            action="store_true",
            dest="silent",
            help="Silence most of the build output.",
        )

    def handle_regeneration(self, event, silent=False):
        regenerate_css.apply_async(args=(event.pk,))
        if not silent:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{event.slug}] Event style was successfully regenerated."
                )
            )

    def handle(self, *args, **options):
        event = options.get("event")
        silent = 1 if options.get("silent") else 0
        if event:
            try:
                event = Event.objects.get(slug__iexact=event)
            except Event.DoesNotExist:
                self.stdout.write(self.style.ERROR("This event does not exist."))
                return
            self.handle_regeneration(event, silent=silent)
        else:
            for event in Event.objects.all():
                self.handle_regeneration(event, silent=silent)
