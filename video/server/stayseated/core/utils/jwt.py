from contextlib import suppress

import jwt

from stayseated.core.services.event import get_event_config


async def decode_token(token, event):
    config = await get_event_config(event)
    for jwt_config in config["event"]["JWT_secrets"]:
        secret = jwt_config["secret"]
        audience = jwt_config["audience"]
        issuer = jwt_config["issuer"]
        with suppress(jwt.exceptions.InvalidSignatureError):
            return jwt.decode(
                token, secret, algorithms=["HS256"], audience=audience, issuer=issuer
            )
