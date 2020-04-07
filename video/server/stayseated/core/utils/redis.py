from channels.layers import get_channel_layer


def aioredis():
    # TODO: we're assuming there is no sharding
    return get_channel_layer().connection(0)
