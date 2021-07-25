from channels_redis.pubsub import RedisPubSubChannelLayer


class ChannelLayer(RedisPubSubChannelLayer):
    async def group_discard(self, group, channel):
        # Silently fail if group currently not subscribed
        group_channel = self._get_group_channel_name(group)
        if group_channel not in self.groups:
            return
        group_channels = self.groups[group_channel]
        if channel not in group_channels:
            return
        return await super().group_discard(group, channel)
