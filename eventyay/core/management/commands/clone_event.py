import datetime
import uuid

import jwt
from django.core.management.base import BaseCommand

from eventyay.base.models import Event


class Command(BaseCommand):
    help = "Clone an event (with rooms and configuration)"

    def add_arguments(self, parser):
        parser.add_argument("event_id", type=str)
        parser.add_argument("--new-secrets", action="store_true")

    def handle(self, *args, **options):
        old = Event.objects.get(id=options["event_id"])
        new = Event()

        while True:
            v = input("Enter the internal ID for the new event (alphanumeric): ")
            if v.strip() and v.strip().isalnum():
                if Event.objects.filter(id=v.strip()).exists():
                    print("This event already exists.")
                else:
                    new.id = v
                    break

        new.title = input("Enter the title for the new event: ")
        new.domain = input(
            "Enter the domain of the new event (e.g. myevent.example.org): "
        )

        new.clone_from(old, new_secrets=options["new_secrets"])
        print("Event cloned.")

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
        token = jwt.encode(payload, jwt_config["secret"], algorithm="HS256")
        print(f"https://{new.domain}/#token={token}")
