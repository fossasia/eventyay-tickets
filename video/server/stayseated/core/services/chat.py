from channels.db import database_sync_to_async
from django.db import IntegrityError
from django.db.models import Max

from ..models import ChatEvent
from ..serializers.chat import ChatEventSerializer
from ..utils.redis import aioredis
from .user import get_public_users, get_user_by_id


class ChatService:
    def __init__(self, world_id):
        self.world_id = world_id

    async def get_channel_uids(self, channel):
        async with aioredis() as redis:
            return [
                u.decode() for u in await redis.smembers(f"channel:{channel}:userset")
            ]

    async def get_channel_users(self, channel):
        uids = await self.get_channel_uids(channel)
        users = await get_public_users(ids=uids, world_id=self.world_id)
        return users

    async def add_channel_user(self, channel, uid):
        async with aioredis() as redis:
            await redis.sadd(f"channel:{channel}:userset", uid)

    async def remove_channel_user(self, channel, uid):
        async with aioredis() as redis:
            await redis.srem(f"channel:{channel}:userset", uid)

    @database_sync_to_async
    def _store_event(self, channel, id, event_type, content, sender):
        ce = ChatEvent.objects.create(
            id=id,
            world_id=self.world_id,
            channel=channel,
            event_type=event_type,
            content=content,
            sender=sender,
        )
        return ChatEventSerializer().to_representation(ce)

    @database_sync_to_async
    def _get_highest_id(self):
        return ChatEvent.objects.aggregate(m=Max("id"))["m"] or 0

    async def create_event(self, channel, event_type, content, sender, _retry=False):
        async with aioredis() as redis:
            event_id = await redis.incr("chat.event_id")
        try:
            return await self._store_event(
                channel=channel,
                id=event_id,
                event_type=event_type,
                content=content,
                sender=await get_user_by_id(self.world_id, sender),
            )
        except IntegrityError as e:
            if "already exists" in str(e) and not _retry:
                # Ooops! Probably our redis cleared out / failed over. Let's try to self-heal
                async with aioredis() as redis:
                    current_max = await self._get_highest_id()
                    await redis.set("chat.event_id", current_max + 1)
                res = await self.create_event(
                    channel, event_type, content, sender, _retry=True
                )
                return res
            raise e  # pragma: no cover
