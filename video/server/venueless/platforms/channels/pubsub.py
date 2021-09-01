import binascii

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

    def _get_shard(self, channel_or_group_name):
        # There's a bug in channels_redis, which uses hash(), but hash() isn't consistent between machines.
        # We'll file a bug/PR against channels_redis, but for the time being, this fixes the bug.
        if len(self._shards) == 1:
            # Avoid the overhead of hashing and modulo when it is unnecessary.
            return self._shards[0]
        if isinstance(channel_or_group_name, str):
            channel_or_group_name = channel_or_group_name.encode("utf8")
        bigval = binascii.crc32(channel_or_group_name) & 0xFFF
        ring_divisor = 4096 / float(len(self._shards))
        return self._shards[int(bigval / ring_divisor)]
