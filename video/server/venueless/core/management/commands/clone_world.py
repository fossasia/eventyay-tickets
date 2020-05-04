from django.core.management.base import BaseCommand

from venueless.core.models import Channel, World


class Command(BaseCommand):
    help = "Clone a world (with rooms and configuration)"

    def add_arguments(self, parser):
        parser.add_argument("world_id", type=str)

    def handle(self, *args, **options):
        old = World.objects.get(id=options["world_id"])
        new = World.objects.get(id=options["world_id"])
        new.pk = None

        while True:
            v = input("Enter the internal ID for the new world (alphanumeric): ")
            if v.strip() and v.strip().isalnum():
                if World.objects.filter(id=v.strip()).exists():
                    print("This world already exists.")
                new.id = v
                break

        new.title = input("Enter the title for the new world: ")
        new.domain = input(
            "Enter the domain of the new world (e.g. myevent.example.org): "
        )
        new.save()
        for r in old.rooms.all():
            try:
                has_channel = r.channel
            except:
                has_channel = False
            r.pk = None
            r.world = new
            r.save()
            if has_channel:
                Channel.objects.create(room=r, world=new)

        print("World cloned.")
