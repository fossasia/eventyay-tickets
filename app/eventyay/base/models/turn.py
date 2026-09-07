import base64
import hashlib
import hmac
import time
import uuid

from django.db import models
from django.utils.crypto import get_random_string


class TurnServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    hostname = models.CharField(max_length=300)
    auth_secret = models.CharField(max_length=300)
    event_exclusive = models.ForeignKey(
        "Event", null=True, blank=True, on_delete=models.PROTECT
    )
    organizers = models.ManyToManyField(
        "Organizer", blank=True, related_name="turn_servers"
    )
    events = models.ManyToManyField(
        "Event", blank=True, related_name="turn_servers"
    )

    def generate_credentials(self):
        username = get_random_string(16)
        expire = int(time.time()) + (24 * 3600)
        username = f"{expire}:{username}"
        hmacv = hmac.new(
            self.auth_secret.encode(), username.encode(), hashlib.sha256
        ).digest()
        password = base64.b64encode(hmacv).decode()
        return username, password

    def get_ice_servers(self):
        username, credential = self.generate_credentials()
        raw_host = (self.hostname or "").strip()
        if ":" in raw_host:
            host, _ = raw_host.split(":", 1)
        else:
            host = raw_host

        return [
            {
                "urls": f"stun:{raw_host}",
                "username": username,
                "credential": credential,
            },
            {
                "urls": f"turns:{host}:443?transport=tcp",
                "username": username,
                "credential": credential,
            },
            {
                "urls": f"turn:{raw_host}?transport=tcp" if ":" in raw_host else f"turn:{raw_host}:3478?transport=tcp",
                "username": username,
                "credential": credential,
            },
        ]
