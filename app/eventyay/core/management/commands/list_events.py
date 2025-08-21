from django.core.management.base import BaseCommand

from eventyay.base.models import Event


class Command(BaseCommand):
    help = "List all events in the database"

    def handle(self, *args, **options):
        print("{:18}  {:32.32}  {}".format("ID", "Title", "URL"))
        for e in Event.objects.all():
            print(
                "{:18}  {:32.32}  {}".format(
                    e.pk, e.title, "https://" + e.domain if e.domain else ""
                )
            )
