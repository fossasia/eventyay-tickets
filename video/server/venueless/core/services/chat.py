from contextlib import suppress

from channels.db import database_sync_to_async
from django.db import IntegrityError, transaction
from django.db.models import Max

from ..models import Channel, ChatEvent, Membership, User
from ..utils.redis import aioredis
from .user import get_public_users


class ChatService:
    class NotAChannelMember(Exception):
        pass

    def __init__(self, world_id):
        self.world_id = world_id

    @database_sync_to_async
    def get_channels_for_user(self, user_id, is_volatile=None):
        qs = Membership.objects.filter(
            channel__world_id=self.world_id, user_id=user_id,
        )
        if is_volatile is not None:  # pragma: no cover
            qs = qs.filter(volatile=is_volatile)
        return list(str(channel) for channel in qs.values_list("channel", flat=True))

    async def get_channel_users(self, channel):
        users = await get_public_users(
            # We're doing an ORM query in an async method, but it's okay, since it is not going to be evaluated but
            # lazily passed to get_public_users which will use it as a subquery :)
            ids=Membership.objects.filter(channel_id=channel).values_list(
                "user_id", flat=True
            ),
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
    def membership_exists(self, channel, uid):
        return Membership.objects.filter(channel=channel, user_id=uid).exists()

    @database_sync_to_async
    def membership_is_volatile(self, channel, uid):
        try:
            m = Membership.objects.get(channel=channel, user_id=uid)
            return m.volatile
        except Membership.DoesNotExist:  # pragma: no cover
            return False

    @database_sync_to_async
    def add_channel_user(self, channel_id, uid, volatile):
        # Currently, users are undeletable, so this should be a pretty impossible code path. Anyway, if it happens,
        # there is probably no harm in ignoring it.
        with suppress(User.DoesNotExist):
            with transaction.atomic():
                m, created = Membership.objects.get_or_create(
                    channel=Channel.objects.get(id=channel_id),
                    user=User.objects.get(id=uid, world_id=self.world_id),
                    defaults={"volatile": volatile},
                )
                if not created and m.volatile and not volatile:
                    m.volatile = False
                    m.save(update_fields=["volatile"])
                return created

    @database_sync_to_async
    def remove_channel_user(self, channel_id, uid):
        Membership.objects.filter(channel_id=channel_id, user_id=uid,).delete()

    @database_sync_to_async
    def get_events(self, channel, before_id, count=50):
        events = ChatEvent.objects.filter(id__lt=before_id, channel=channel,).order_by(
            "-id"
        )[: min(count, 1000)]
        return [e.serialize_public() for e in reversed(list(events))]

    @database_sync_to_async
    def _store_event(self, channel_id, id, event_type, content, sender):
        ce = ChatEvent.objects.create(
            id=id,
            channel=Channel.objects.get(id=channel_id),
            event_type=event_type,
            content=content,
            sender=sender,
        )
        return ce.serialize_public()

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
        if event_type not in ("channel.member",) and not await self.membership_exists(
            channel, sender
        ):
            raise self.NotAChannelMember()
        try:
            return await self._store_event(
                channel_id=channel,
                id=event_id,
                event_type=event_type,
                content=content,
                sender=sender,
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
