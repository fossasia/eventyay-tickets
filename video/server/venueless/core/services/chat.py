from contextlib import suppress

from channels.db import database_sync_to_async
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, OuterRef, Prefetch, Q, Subquery
from django.utils.timezone import now

from ..models import Channel, ChatEvent, Membership, User
from ..utils.redis import aioredis
from .user import get_public_users


@database_sync_to_async
def _get_channel(**kwargs):
    return (
        Channel.objects.filter(Q(room__isnull=True) | Q(room__deleted=False))
        .select_related("world", "room")
        .get(**kwargs)
    )


async def get_channel(**kwargs):
    with suppress(
        Channel.DoesNotExist, Channel.MultipleObjectsReturned, ValidationError
    ):
        c = await _get_channel(**kwargs)
        return c


class ChatService:
    def __init__(self, world_id):
        self.world_id = world_id

    def get_channels_for_user(self, user_id, is_volatile=None):
        qs = (
            Membership.objects.filter(channel__world_id=self.world_id, user_id=user_id,)
            .annotate(max_id=Max("channel__chat_events__id"))
            .prefetch_related(
                Prefetch(
                    "channel",
                    queryset=Channel.objects.prefetch_related(
                        Prefetch(
                            "members",
                            Membership.objects.filter(
                                channel__room__isnull=True
                            ).select_related("user"),
                            to_attr="direct_members",
                        )
                    ),
                )
            )
        )
        if is_volatile is not None:  # pragma: no cover
            qs = qs.filter(volatile=is_volatile)
        res = []
        for m in qs:
            r = {
                "id": str(m.channel_id),
                "notification_pointer": m.max_id,
            }
            if not m.channel.room_id:
                r["members"] = [
                    m.user.serialize_public() for m in m.channel.direct_members
                ]
            res.append(r)
        return res

    async def get_channel_users(self, channel, include_admin_info=False):
        users = await get_public_users(
            # We're doing an ORM query in an async method, but it's okay, since it is not going to be evaluated but
            # lazily passed to get_public_users which will use it as a subquery :)
            ids=Membership.objects.filter(channel_id=channel).values_list(
                "user_id", flat=True
            ),
            world_id=self.world_id,
            include_admin_info=include_admin_info,
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
            m = Membership.objects.get(channel=channel, user_id=uid)
            return m.volatile
        except Membership.DoesNotExist:  # pragma: no cover
            return False

    @database_sync_to_async
    def add_channel_user(self, channel_id, user, volatile):
        # Currently, users are undeletable, so this should be a pretty impossible code path. Anyway, if it happens,
        # there is probably no harm in ignoring it.
        with suppress(User.DoesNotExist):
            with transaction.atomic():
                m, created = Membership.objects.get_or_create(
                    channel_id=channel_id, user=user, defaults={"volatile": volatile},
                )
                if not created and m.volatile and not volatile:
                    m.volatile = False
                    m.save(update_fields=["volatile"])
                return created

    @database_sync_to_async
    def remove_channel_user(self, channel_id, uid):
        Membership.objects.filter(channel_id=channel_id, user_id=uid,).delete()

    @database_sync_to_async
    def get_events(self, channel, before_id, count=50, skip_membership=False):
        events = ChatEvent.objects
        if skip_membership:
            events = events.exclude(event_type="channel.member")
        events = events.filter(id__lt=before_id, channel=channel,).order_by("-id")[
            : min(count, 1000)
        ]
        return [e.serialize_public() for e in reversed(list(events))]

    @database_sync_to_async
    def _store_event(self, channel_id, id, event_type, content, sender, replaces=None):
        ce = ChatEvent.objects.create(
            id=id,
            channel_id=channel_id,
            event_type=event_type,
            content=content,
            sender=sender,
            replaces_id=replaces,
        )
        return ce.serialize_public()

    @database_sync_to_async
    def get_highest_id_in_channel(self, channel_id):
        return (
            ChatEvent.objects.filter(channel_id=channel_id).aggregate(m=Max("id"))["m"]
            or 0
        )

    @database_sync_to_async
    def _get_highest_id(self):
        return ChatEvent.objects.aggregate(m=Max("id"))["m"] or 0

    async def get_last_id(self):
        async with aioredis() as redis:
            rval = await redis.get("chat.event_id", encoding="utf-8")
            if rval:
                return int(rval)
            return 0

    async def create_event(
        self, channel_id, event_type, content, sender, replaces=None, _retry=False
    ):
        async with aioredis() as redis:
            event_id = await redis.incr("chat.event_id")
        try:
            return await self._store_event(
                channel_id=channel_id,
                id=event_id,
                event_type=event_type,
                content=content,
                sender=sender,
                replaces=replaces,
            )
        except IntegrityError as e:
            if "already exists" in str(e) and not _retry:
                # Ooops! Probably our redis cleared out / failed over. Let's try to self-heal
                async with aioredis() as redis:
                    current_max = await self._get_highest_id()
                    await redis.set("chat.event_id", current_max + 1)
                res = await self.create_event(
                    channel_id, event_type, content, sender, _retry=True
                )
                return res
            raise e  # pragma: no cover

    @database_sync_to_async
    def get_or_create_direct_channel(self, user_ids):
        with transaction.atomic():
            users = list(
                User.objects.prefetch_related("blocked_users").filter(
                    world_id=self.world_id, id__in=user_ids
                )
            )
            if (
                len(users) != len(user_ids)
                or len(users) < 2
                or any(
                    any(v in u.blocked_users.all() for v in users if v != u)
                    for u in users
                )
            ):
                return None, False, []
            try:
                return (
                    Channel.objects.annotate(
                        mcount_match=Subquery(
                            Membership.objects.filter(
                                channel=OuterRef("pk"), user_id__in=user_ids
                            )
                            .order_by()
                            .values("channel")
                            .annotate(c=Count("*"))
                            .values("c")
                        ),
                        mcount_mismatch=Subquery(
                            Membership.objects.filter(channel=OuterRef("pk"),)
                            .exclude(user_id__in=user_ids)
                            .order_by()
                            .values("channel")
                            .annotate(c=Count("*"))
                            .values("c")
                        ),
                    ).get(
                        mcount_mismatch__isnull=True,
                        mcount_match=len(user_ids),
                        room__isnull=True,
                        world_id=self.world_id,
                    ),
                    False,
                    users,
                )
            except Channel.DoesNotExist:
                c = Channel.objects.create(room=None, world_id=self.world_id)
                for u in users:
                    Membership.objects.create(channel=c, user=u, volatile=False)

                return c, True, users

    @database_sync_to_async
    def get_event(self, **kwargs):
        return ChatEvent.objects.get(**kwargs)

    @database_sync_to_async
    def update_event(self, event, new_content):
        event.content = new_content
        event.edited = now()
        event.save()
        return event
