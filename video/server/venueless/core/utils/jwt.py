from contextlib import suppress

import jwt

from venueless.core.services.world import get_world


async def decode_token(token, world_id):
    world = await get_world(world_id)
    for jwt_config in world.config["JWT_secrets"]:
        secret = jwt_config["secret"]
        audience = jwt_config["audience"]
        issuer = jwt_config["issuer"]
        with suppress(jwt.exceptions.InvalidSignatureError):
            return jwt.decode(
                token, secret, algorithms=["HS256"], audience=audience, issuer=issuer
            )
