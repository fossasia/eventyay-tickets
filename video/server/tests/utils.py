import datetime as dt
import random

import jwt
from channels.testing import WebsocketCommunicator
from django.utils.crypto import get_random_string


def get_token(world, traits):
    config = world.config["JWT_secrets"][0]

    iat = dt.datetime.utcnow()
    exp = iat + dt.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": random.randint(9999, 99999),
        "traits": traits,
    }
    return jwt.encode(payload, config["secret"], algorithm="HS256")


def get_token_header(world, traits=["admin", "api"]):
    token = get_token(world, traits)
    return "Bearer " + token


class LoggingCommunicator(WebsocketCommunicator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._log_id = get_random_string(6)

    async def connect(self, *args, **kwargs):
        print(f"{self._log_id}  CONNECT")
        return await super().connect(*args, **kwargs)

    async def disconnect(self, *args, **kwargs):
        print(f"{self._log_id}  DISCONNECT")
        return await super().disconnect(*args, **kwargs)

    async def send_to(self, text_data=None, bytes_data=None):
        print(f"{self._log_id}  SEND  {text_data or bytes_data}")
        return await super().send_to(text_data, bytes_data)

    async def receive_from(self, timeout=1):
        r = await super().receive_from(timeout)
        print(f"{self._log_id}  RECV  {r}")
        return r
