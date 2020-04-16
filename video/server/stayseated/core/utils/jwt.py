from contextlib import suppress

import jwt

from stayseated.core.services.world import get_world_config


async def decode_token(token, world):
    config = await get_world_config(world)
    for jwt_config in config["world"]["JWT_secrets"]:
        secret = jwt_config["secret"]
        audience = jwt_config["audience"]
        issuer = jwt_config["issuer"]
        with suppress(jwt.exceptions.InvalidSignatureError):
            return jwt.decode(
                token, secret, algorithms=["HS256"], audience=audience, issuer=issuer
            )
