import datetime as dt
import random

import jwt


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
    return jwt.encode(payload, config["secret"], algorithm="HS256").decode("utf-8")


def get_token_header(world, traits=["admin", "api"]):
    token = get_token(world, traits)
    return "Bearer " + token
