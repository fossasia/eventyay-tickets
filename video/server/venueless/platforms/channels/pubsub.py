from channels_redis.pubsub import RedisPubSubChannelLayer


class ChannelLayer(RedisPubSubChannelLayer):
    async def group_discard(self, group, channel):
        # Silently fail if group currently not subscribed
        l = self._get_layer()
        group_channel = l._get_group_channel_name(group)
        if group_channel not in l.groups:
            return
        group_channels = l.groups[group_channel]
        if channel not in group_channels:
            return
        return await super()._proxy('group_discard', group, channel)
