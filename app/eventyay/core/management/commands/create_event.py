import datetime
import uuid

import jwt
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string

from eventyay.base.models import Event


class Command(BaseCommand):
    help = "Create a new event"

    def handle(self, *args, **options):
        e = Event()
        while True:
            v = input("Enter the internal ID for the new event (alphanumeric): ")
            if v.strip() and v.strip().isalnum():
                if Event.objects.filter(id=v.strip()).exists():
                    print("This event already exists.")
                e.id = v
                break

        e.title = input("Enter the title for the new event: ")
        e.domain = input(
            "Enter the domain of the new event (e.g. myevent.example.org): "
        )

        secret = get_random_string(length=64)
        e.config = {
            "JWT_secrets": [
                {
                    "issuer": "any",
                    "audience": "eventyay",
                    "secret": secret,
                }
            ]
        }
        e.save()

        print("Event created.")
        print("Default API key secrets:", e.config["JWT_secrets"])

        print("Admin url:")
        iat = datetime.datetime.utcnow()
        exp = iat + datetime.timedelta(days=365)
        payload = {
            "iss": "any",
            "aud": "eventyay",
            "exp": exp,
            "iat": iat,
            "uid": str(uuid.uuid4()),
            "traits": ["admin"],
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        print(f"https://{e.domain}/#token={token}")
