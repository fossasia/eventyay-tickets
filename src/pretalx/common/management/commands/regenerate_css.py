from django.core.management.base import BaseCommand

from pretalx.common.tasks import regenerate_css
from pretalx.event.models.event import Event


class Command(BaseCommand):
    help = "Rebuild static files and language files"

    def add_arguments(self, parser):
        parser.add_argument("--event", type=str)

    def handle_regeneration(self, event):
        regenerate_css.apply_async(args=(event.pk,))
        self.stdout.write(
            self.style.SUCCESS(
                f"[{event.slug}] Event style was successfully regenerated."
            )
        )

    def handle(self, *args, **options):
        event = options.get("event")
        if event:
            try:
                event = Event.objects.get(slug__iexact=event)
            except Event.DoesNotExist:
                self.stdout.write(self.style.ERROR("This event does not exist."))
                return
            self.handle_regeneration(event)
        else:
            for event in Event.objects.all():
                self.handle_regeneration(event)
