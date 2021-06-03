from datetime import timedelta

from channels.db import database_sync_to_async
from django.db import DatabaseError, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils.timezone import now

from venueless.core.models import RoulettePairing, RouletteRequest, User


@database_sync_to_async
def roulette_request(user, room, socket_id, module_config):
    try:
        INTERVAL_REMATCH = timedelta(
            minutes=int(module_config.get("rematch_interval", 24 * 60))
        )
    except:
        INTERVAL_REMATCH = timedelta(minutes=24 * 60)

    with transaction.atomic():
        # Lock previous request, if it exists
        try:
            own = (
                RouletteRequest.objects.select_for_update(nowait=True)
                .filter(user=user, room=room, socket_id=socket_id)
                .first()
            )
        except DatabaseError:
            # someone else just selected me! let's wait for the handshake to complete.
            return None

        # Find if there's a proper pairing partner waiting for us, and lock it
        waiting = list(
            RouletteRequest.objects.select_for_update(skip_locked=True)
            .annotate(
                is_blocked_by_me=Exists(
                    User.blocked_users.through.objects.filter(
                        from_user=user,
                        to_user=OuterRef("user"),
                    )
                ),
                is_blocked_by_other=Exists(
                    User.blocked_users.through.objects.filter(
                        from_user=OuterRef("user"),
                        to_user=user,
                    )
                ),
                previously_seen=Exists(
                    RoulettePairing.objects.filter(
                        room=room,
                        user1=OuterRef("user"),
                        user2=user,
                        timestamp__gte=now() - INTERVAL_REMATCH,
                    )
                ),
                previously_seen_by=Exists(
                    RoulettePairing.objects.filter(
                        room=room,
                        user2=OuterRef("user"),
                        user1=user,
                        timestamp__gte=now() - INTERVAL_REMATCH,
                    )
                ),
            )
            .filter(
                Q(room=room)
                & ~Q(user=user)
                & Q(expiry__gte=now())
                & Q(is_blocked_by_me=False)
                & Q(is_blocked_by_other=False)
                & Q(previously_seen=False)
                & Q(previously_seen_by=False)
            )
            .select_related("user")[:1]
        )

        if waiting:
            # There is someone waiting
            pairing = RoulettePairing.objects.create(
                room=room, user1=user, user2=waiting[0].user
            )
            if own:
                own.delete()
            waiting[0].delete()
            return waiting[0], str(pairing.pk), -1
        else:
            # There isn't someone waiting, let's wait
            if own:
                own.expiry = now() + timedelta(seconds=30)
                own.save()
            else:
                RouletteRequest.objects.create(
                    room=room,
                    user=user,
                    socket_id=socket_id,
                    expiry=now() + timedelta(seconds=30),
                )
            recent_pairs = (
                RoulettePairing.objects.filter(
                    room=room,
                    timestamp__gte=now() - timedelta(minutes=5),
                )
                .exclude(Q(user1=user) | Q(user2=user))
                .count()
            )
            return own, None, recent_pairs


@database_sync_to_async
def roulette_cleanup(socket_id):
    RouletteRequest.objects.filter(socket_id=socket_id).delete()


@database_sync_to_async
def is_member_of_roulette_call(call_id, user):
    try:
        p = RoulettePairing.objects.get(id=call_id)
        return p.user1_id == user.pk or p.user2_id == user.pk
    except RoulettePairing.DoesNotExist:
        return False
