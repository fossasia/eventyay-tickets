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
    world_exclusive = models.ForeignKey(
        "World", null=True, blank=True, on_delete=models.PROTECT
    )

    def generate_credentials(self):
        username = get_random_string(16)
        expire = int(time.time()) + (24 * 3600)
        username = f"{expire}:{username}"
        hmacv = hmac.new(
            self.auth_secret.encode(), username.encode(), hashlib.sha1
        ).digest()
        password = base64.b64encode(hmacv).decode()
        return username, password

    def get_ice_servers(self):
        username, credential = self.generate_credentials()
        return [
            {
                "urls": f"stun:{self.hostname}",
                "username": username,
                "credential": credential,
            },
            {
                "urls": f"turns:{self.hostname}:443?transport=tcp",
                "username": username,
                "credential": credential,
            },
            {
                "urls": f"turn:{self.hostname}:443?transport=tcp",
                "username": username,
                "credential": credential,
            },
        ]
