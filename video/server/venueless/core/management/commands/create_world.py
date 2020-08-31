import datetime
import uuid

import jwt
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

        secret = get_random_string(length=64)
        w.config = {
            "JWT_secrets": [
                {
                    "issuer": "any",
                    "audience": "venueless",
                    "secret": secret,
                }
            ]
        }
        w.trait_grants["admin"] = ["admin"]
        w.save()

        print("World created.")
        print("Default API key secrets:", w.config["JWT_secrets"])

        print("Admin url:")
        iat = datetime.datetime.utcnow()
        exp = iat + datetime.timedelta(days=365)
        payload = {
            "iss": "any",
            "aud": "venueless",
            "exp": exp,
            "iat": iat,
            "uid": str(uuid.uuid4()),
            "traits": ["admin"],
        }
        token = jwt.encode(payload, secret, algorithm="HS256").decode("utf-8")
        print(f"https://{w.domain}/#token={token}")
