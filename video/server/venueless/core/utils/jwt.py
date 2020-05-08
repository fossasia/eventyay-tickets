from venueless.core.services.world import get_world


async def decode_token(token, world_id):
    world = await get_world(world_id)
    return world.decode_token(token)
