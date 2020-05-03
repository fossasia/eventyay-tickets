from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string

from venueless.core.models import World


class Command(BaseCommand):
    help = "Create a new world"

    def handle(self, *args, **options):
        w = World()
        while True:
            v = input("Enter the internal ID for the new world (alphanumeric): ")
            if v.strip() and v.strip().isalnum():
                if World.objects.filter(id=v.strip()).exists():
                    print("This world already exists.")
                w.id = v
                break

        w.title = input("Enter the title for the new world: ")
        w.domain = input(
            "Enter the domain of the new world (e.g. myevent.example.org): "
        )

        w.config = {
            "JWT_secrets": [
                {
                    "issuer": "any",
                    "audience": "venueless",
                    "secret": get_random_string(length=64),
                }
            ]
        }
        w.save()

        print("World created.")
        print("Default API key secrets:", w.config["JWT_secrets"])
