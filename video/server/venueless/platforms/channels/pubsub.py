from channels_redis.pubsub import RedisPubSubChannelLayer


class ChannelLayer(RedisPubSubChannelLayer):
    async def group_discard(self, group, channel):
        # Silently fail if group currently not subscribed
        layer = self._get_layer()
        group_channel = layer._get_group_channel_name(group)
        if group_channel not in layer.groups:
            return
        group_channels = layer.groups[group_channel]
        if channel not in group_channels:
            return
        return await super()._proxy("group_discard", group, channel)
