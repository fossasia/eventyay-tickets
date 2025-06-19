from django.core.management.base import BaseCommand

from venueless.core.models import World


class Command(BaseCommand):
    help = "List all worlds in the database"

    def handle(self, *args, **options):
        print("{:18}  {:32.32}  {}".format("ID", "Title", "URL"))
        for w in World.objects.all():
            print(
                "{:18}  {:32.32}  {}".format(
                    w.pk, w.title, "https://" + w.domain if w.domain else ""
                )
            )
