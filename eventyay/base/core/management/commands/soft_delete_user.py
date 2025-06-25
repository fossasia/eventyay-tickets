from django.core.management.base import BaseCommand

from venueless.core.models import User


class Command(BaseCommand):
    help = "Anonymize a user"

    def add_arguments(self, parser):
        parser.add_argument("user_id", type=str)

    def handle(self, *args, **options):
        w = User.objects.get(id=options["user_id"])
        w.soft_delete()
