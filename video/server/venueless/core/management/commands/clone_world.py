import datetime
import uuid

import jwt
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string

from venueless.core.models import Channel, World


class Command(BaseCommand):
    help = "Clone a world (with rooms and configuration)"

    def add_arguments(self, parser):
        parser.add_argument("world_id", type=str)
        parser.add_argument("--new-secrets", action="store_true")

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

        if options["new_secrets"]:
            secret = get_random_string(length=64)
            new.config['JWT_secrets'] = [
                {
                    "issuer": "any",
                    "audience": "venueless",
                    "secret": secret,
                }
            ]

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

        print("Default API key secrets:", new.config["JWT_secrets"])

        jwt_config = new.config["JWT_secrets"][0]
        print("Admin url:")
        iat = datetime.datetime.utcnow()
        exp = iat + datetime.timedelta(days=365)
        payload = {
            "iss": jwt_config["issuer"],
            "aud": jwt_config["audience"],
            "exp": exp,
            "iat": iat,
            "uid": str(uuid.uuid4()),
            "traits": ["admin"],
        }
        token = jwt.encode(payload, jwt_config["secret"], algorithm="HS256").decode(
            "utf-8"
        )
        print(f"https://{new.domain}/#token={token}")
