import datetime
import random
import string
import uuid

import jwt
from django.db import models


class StreamingServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    name = models.CharField(max_length=300)
    token_secret = models.CharField(max_length=300)
    url_input = models.CharField(
        max_length=300, default="rtmp://server/app/{name}?token={token}"
    )
    url_output = models.CharField(
        max_length=300, default="https://server/hls/{name}.m3u8"
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)

    def generate_streamkey(self, name, days):
        iat = datetime.datetime.utcnow()

        n = name + "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(8)
        )

        token = jwt.encode(
            {"name": n, "iat": iat, "exp": iat + datetime.timedelta(days=days)},
            self.token_secret,
            algorithm="HS256",
        )
        ui = self.url_input.format(name=n, token=token)
        return {
            "input": ui,
            "input_server": ui.rsplit("/", 1)[0] + "/",
            "input_key": ui.rsplit("/", 1)[1] if "/" in ui else "",
            "output": self.url_output.format(name=n),
        }
