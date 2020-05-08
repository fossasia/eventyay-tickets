import datetime

import jwt


def get_token_header(world, traits=["admin", "api"]):
    config = world.config["JWT_secrets"][0]

    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": traits,
    }
    token = jwt.encode(payload, config["secret"], algorithm="HS256").decode("utf-8")
    return "Bearer " + token
