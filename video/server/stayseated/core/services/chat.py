from channels.db import database_sync_to_async
from django.db import IntegrityError, transaction
from django.db.models import Max

from ..models import ChatEvent, User
from ..models.chat import Membership
from ..serializers.chat import ChatEventSerializer
from ..utils.redis import aioredis
from .user import get_public_users, get_user_by_id


class ChatService:
    def __init__(self, world_id):
        self.world_id = world_id

    @database_sync_to_async
    def get_channels_for_user(self, user_id, is_volatile=None):
        qs = Membership.objects.filter(world_id=self.world_id, user_id=user_id,)
        if is_volatile is not None:  # pragma: no cover
            qs = qs.filter(volatile=is_volatile)
        return list(qs.values_list("channel", flat=True))

    async def get_channel_users(self, channel):
        users = await get_public_users(
            # We're doing an ORM query in an async method, but it's okay, since it is not going to be evaluated but
            # lazily passed to get_public_users which will use it as a subquery :)
            ids=Membership.objects.filter(
                world_id=self.world_id, channel=channel
            ).values_list("user_id", flat=True),
            world_id=self.world_id,
        )
        return users

    async def track_subscription(self, channel, uid, socket_id):
        async with aioredis() as redis:
            await redis.sadd(f"chat:subscriptions:{uid}:{channel}", socket_id)

    async def track_unsubscription(self, channel, uid, socket_id):
        async with aioredis() as redis:
            await redis.srem(f"chat:subscriptions:{uid}:{channel}", socket_id)
            return await redis.scard(f"chat:subscriptions:{uid}:{channel}")

    @database_sync_to_async
    def membership_is_volatile(self, channel, uid):
        try:
            m = Membership.objects.get(
                world_id=self.world_id, channel=channel, user_id=uid,
            )
            return m.volatile
        except Membership.DoesNotExist:  # pragma: no cover
            return False

    @database_sync_to_async
    def add_channel_user(self, channel, uid, volatile):
        try:
            with transaction.atomic():
                m, created = Membership.objects.get_or_create(
                    world_id=self.world_id,
                    channel=channel,
                    user=User.objects.get(id=uid, world_id=self.world_id),
                    defaults={"volatile": volatile},
                )
                if not created and m.volatile and not volatile:
                    m.volatile = False
                    m.save(update_fields=["volatile"])
                return created
        except User.DoesNotExist:  # pragma: no cover
            # Currently, users are undeletable, so this should be a pretty impossible code path. Anyway, if it happens,
            # there is probably no harm in ignoring it.
            return False

    @database_sync_to_async
    def remove_channel_user(self, channel, uid):
        Membership.objects.filter(
            world_id=self.world_id, channel=channel, user_id=uid,
        ).delete()

    @database_sync_to_async
    def get_events(self, channel, before_id, count=50):
        events = ChatEvent.objects.filter(
            id__lt=before_id, world_id=self.world_id, channel=channel,
        ).order_by("-id")[: min(count, 1000)]
        return ChatEventSerializer(reversed(list(events)), many=True).data

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

    async def get_last_id(self):
        async with aioredis() as redis:
            rval = await redis.get("chat.event_id", encoding="utf-8")
            if rval:
                return int(rval)
            return 0

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
