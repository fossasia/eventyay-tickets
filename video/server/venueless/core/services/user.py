import operator
from collections import namedtuple
from datetime import timedelta
from functools import reduce

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core.paginator import InvalidPage, Paginator
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.timezone import now

from ...live.channels import GROUP_USER
from ..models import AuditLog
from ..models.auth import User
from ..models.world import WorldView
from ..permissions import Permission


def get_user_by_id(world_id, user_id):
    try:
        return User.objects.get(id=user_id, world_id=world_id)
    except User.DoesNotExist:
        return


def get_user_by_token_id(world_id, token_id):
    try:
        return User.objects.get(token_id=token_id, world_id=world_id)
    except User.DoesNotExist:
        return


def get_user_by_client_id(world_id, client_id):
    try:
        return User.objects.get(client_id=client_id, world_id=world_id)
    except User.DoesNotExist:
        return


@database_sync_to_async
def get_public_user(world_id, id, include_admin_info=False, trait_badges_map=None):
    user = get_user_by_id(world_id, id)
    if not user:
        return None
    return user.serialize_public(
        include_admin_info=include_admin_info, trait_badges_map=trait_badges_map
    )


@database_sync_to_async
def get_public_users(
    world_id,
    *,
    ids=None,
    pretalx_ids=None,
    include_admin_info=False,
    trait_badges_map=None,
    include_banned=True,
):
    # This method is called a lot, especially when lots of people join at once (event start, server reboot, …)
    # For performance reasons, we therefore do not initialize model instances and use serialize_public()
    if ids is not None:
        qs = User.objects.filter(id__in=ids, world_id=world_id)
    else:
        qs = User.objects.filter(world_id=world_id).order_by(
            "profile__display_name", "id"
        )
    if pretalx_ids is not None:
        qs = qs.filter(pretalx_id__in=pretalx_ids)
    if not include_banned:
        qs = qs.exclude(moderation_state=User.ModerationState.BANNED)
    return [
        dict(
            id=str(u["id"]),
            profile=u["profile"],
            pretalx_id=u["pretalx_id"],
            inactive=(
                u["last_login"] is None or u["last_login"] < now() - timedelta(hours=36)
            ),
            badges=sorted(
                list(
                    {
                        badge
                        for trait, badge in trait_badges_map.items()
                        if trait in u["traits"]
                    }
                )
            )
            if trait_badges_map
            else [],
            **(
                {"moderation_state": u["moderation_state"], "token_id": u["token_id"]}
                if include_admin_info
                else {}
            ),
        )
        for u in qs.values(
            "id",
            "profile",
            "moderation_state",
            "token_id",
            "traits",
            "last_login",
            "pretalx_id",
        )
    ]


def get_user(
    world=None,
    *,
    with_id=None,
    with_token=None,
    with_client_id=None,
):
    if with_id:
        user = get_user_by_id(world.id, with_id)
        return user

    token_id = None
    if with_token:
        token_id = with_token["uid"]
        user = get_user_by_token_id(world.id, token_id)
    elif with_client_id:
        user = get_user_by_client_id(world.id, with_client_id)
    else:
        raise Exception(
            "get_user was called without valid with_token, with_id or with_client_id"
        )

    if user:
        if with_token and (user.traits != with_token.get("traits")):
            traits = with_token["traits"]
            update_user(world.id, id=user.id, traits=traits)
            user = get_user_by_id(world.id, user.id)
        return user

    traits = with_token.get("traits") if with_token else None
    if not world.has_permission_implicit(
        traits=traits or [], permissions=[Permission.WORLD_VIEW]
    ):
        # There is no chance this user gets in, we want to do an early out to prevent empty
        # user profiles from being created
        return

    if token_id:
        user = create_user(
            world_id=world.id,
            token_id=token_id,
            profile=with_token.get("profile") if with_token else None,
            traits=traits,
            pretalx_id=with_token.get("pretalx_id") if with_token else None,
        )
    else:
        user = create_user(
            world_id=world.id,
            client_id=with_client_id,
            traits=traits,
        )
    return user


def create_user(
    world_id,
    *,
    token_id=None,
    client_id=None,
    traits=None,
    profile=None,
    pretalx_id=None,
):
    return User.objects.create(
        world_id=world_id,
        token_id=token_id,
        client_id=client_id,
        pretalx_id=pretalx_id,
        traits=traits or [],
        profile=profile or {},
    )


@atomic
def update_user(world_id, id, *, traits=None, public_data=None, serialize=True):
    # TODO: Exception handling
    user = (
        User.objects.select_related("world")
        .select_for_update()
        .get(id=id, world_id=world_id)
    )

    if traits is not None:
        if user.traits != traits:
            AuditLog.objects.create(
                world_id=world_id,
                user=user,
                type="auth.user.traits.changed",
                data={"object": str(user.pk), "old": user.traits, "new": traits},
            )
            user.traits = traits
        user.save(update_fields=["traits"])

    if public_data is not None:
        save_fields = []
        if "profile" in public_data and public_data["profile"] != user.profile:
            AuditLog.objects.create(
                world_id=world_id,
                user=user,
                type="auth.user.profile.changed",
                data={
                    "object": str(user.pk),
                    "old": user.profile,
                    "new": public_data["profile"],
                },
            )

            # TODO: Anything we want to validate here?
            user.profile = public_data.get("profile")
            save_fields.append("profile")

        if "pretalx_id" in public_data and public_data["pretalx_id"] != user.pretalx_id:
            AuditLog.objects.create(
                world_id=world_id,
                user=user,
                type="auth.user.pretalx_id.changed",
                data={
                    "object": str(user.pk),
                    "old": user.pretalx_id,
                    "new": public_data["pretalx_id"],
                },
            )
            user.pretalx_id = public_data.get("pretalx_id")
            save_fields.append("pretalx_id")

        if save_fields:
            user.save(update_fields=save_fields)

    return (
        user.serialize_public(
            trait_badges_map=user.world.config.get("trait_badges_map")
        )
        if serialize
        else user
    )


def start_view(user: User, delete=False):
    # The majority of WorldView that go "abandoned" (i.e. ``end`` is never set) are likely caused by server
    # crashes or restarts, in which case ``end`` can't be set. However, after a server crash, the client
    # either reconnects automatically or the user will attempt a reconnect themselves through a page reload,
    # so the most likely end of the previous session is "just before this", and the best assumption is to set
    # the end to "now".
    #
    # Obviously, this is wrong whenever a user has multiple sessions open, e.g. if the same user has the room
    # open in browser A and then opens the same room in browser B, this will set the ``end`` for the session
    # in browser A, even though it's already running. It doesn't matter, though! First, for all our statistics
    # we only count unique users and the result "this user was present at the time" is still correct. Second,
    # the way ``end_view`` is implemented, the session from browser A will still be corrected with the accurate
    # time as soon as browser A leaves.
    previous = WorldView.objects.filter(
        user=user, world_id=user.world_id, end__isnull=True
    )
    if delete:
        previous.delete()
    else:
        previous.update(end=now())
    r = WorldView.objects.create(world_id=user.world_id, user=user)
    return r


def end_view(view: WorldView, delete=False):
    if delete:
        if view.pk:
            view.delete()
    else:
        view.end = now()
        view.save()


LoginResult = namedtuple(
    "LoginResult", "user world_config chat_channels exhibition_data view"
)


def login(
    *,
    world=None,
    token=None,
    client_id=None,
) -> LoginResult:
    from .chat import ChatService
    from .exhibition import ExhibitionService
    from .world import get_world_config_for_user

    user = get_user(world=world, with_client_id=client_id, with_token=token)

    if (
        not user
        or user.is_banned
        or not world.has_permission(user=user, permission=Permission.WORLD_VIEW)
    ):
        return

    user.last_login = now()
    user.save(update_fields=["last_login"])

    if world.config.get("track_world_views", False):
        view = start_view(user)
    else:
        view = None

    return LoginResult(
        user=user,
        world_config=get_world_config_for_user(world, user),
        chat_channels=ChatService(world).get_channels_for_user(
            user.pk, is_volatile=False
        ),
        exhibition_data=ExhibitionService(world).get_exhibition_data_for_user(user.pk),
        view=view,
    )


@database_sync_to_async
@atomic
def get_blocked_users(user, world) -> bool:
    return [
        u.serialize_public(trait_badges_map=world.config.get("trait_badges_map"))
        for u in user.blocked_users.all()
    ]


@database_sync_to_async
@atomic
def set_user_banned(world, user_id, by_user) -> bool:
    user = get_user_by_id(world_id=world.pk, user_id=user_id)
    if not user:
        return False
    user.moderation_state = User.ModerationState.BANNED
    user.save(update_fields=["moderation_state"])

    AuditLog.objects.create(
        world=world,
        user=by_user,
        type="auth.user.banned",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def set_user_silenced(world, user_id, by_user) -> bool:
    user = get_user_by_id(world_id=world.pk, user_id=user_id)
    if not user:
        return False
    if user.moderation_state == User.ModerationState.BANNED:
        return True
    user.moderation_state = User.ModerationState.SILENCED
    user.save(update_fields=["moderation_state"])
    AuditLog.objects.create(
        world=world,
        user=by_user,
        type="auth.user.silenced",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def set_user_free(world, user_id, by_user) -> bool:
    user = get_user_by_id(world_id=world.pk, user_id=user_id)
    if not user:
        return False
    user.moderation_state = User.ModerationState.NONE
    user.save(update_fields=["moderation_state"])
    AuditLog.objects.create(
        world=world,
        user=by_user,
        type="auth.user.reactivated",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def block_user(world, blocking_user: User, blocked_user_id) -> bool:
    blocked_user = get_user_by_id(world_id=world.pk, user_id=blocked_user_id)
    if not blocked_user:
        return False

    blocking_user.blocked_users.add(blocked_user)
    blocked_user.touch()
    AuditLog.objects.create(
        world=world,
        user=blocking_user,
        type="auth.user.blocked",
        data={
            "object": blocked_user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def unblock_user(world, blocking_user: User, blocked_user_id) -> bool:
    blocked_user = get_user_by_id(world_id=world.pk, user_id=blocked_user_id)
    if not blocked_user:
        return False

    blocking_user.blocked_users.remove(blocked_user)
    blocked_user.touch()
    AuditLog.objects.create(
        world=world,
        user=blocking_user,
        type="auth.user.unblocked",
        data={
            "object": blocked_user_id,
        },
    )
    return True


@database_sync_to_async
def list_users(
    world_id,
    page,
    page_size,
    search_term,
    search_fields=None,
    badge=None,
    trait_badges_map=None,
    include_banned=True,
    include_admin_info=False,
) -> object:
    qs = (
        User.objects.filter(world_id=world_id, show_publicly=True)
        .exclude(profile__display_name__isnull=True)
        .exclude(profile__display_name__exact="")
    )
    if not include_banned:
        qs = qs.exclude(moderation_state=User.ModerationState.BANNED)
    if badge:
        conditions = []
        if trait_badges_map:
            for t_trait, t_badge in trait_badges_map.items():
                if t_badge == badge:
                    conditions.append(Q(traits__contains=[t_trait]))
        if conditions:
            qs = qs.filter(reduce(operator.or_, conditions))
        else:
            qs = qs.none()

    if search_term:
        conditions = [(Q(profile__display_name__icontains=search_term))]
        search_fields = search_fields or []
        for field in search_fields:
            conditions.append(
                Q(**{"profile__fields__" + field + "__icontains": search_term})
            )
        qs = qs.filter(reduce(operator.or_, conditions))

    try:
        p = Paginator(
            qs.order_by("profile__display_name").values(
                "id",
                "profile",
                "traits",
                "last_login",
                "moderation_state",
                "token_id",
                "pretalx_id",
            ),
            page_size,
        ).page(page)
        return {
            "results": sorted(
                (
                    dict(
                        id=str(u["id"]),
                        profile=u["profile"],
                        pretalx_id=u["pretalx_id"],
                        inactive=u["last_login"] is None
                        or u["last_login"] < now() - timedelta(hours=36),
                        badges=sorted(
                            list(
                                {
                                    badge
                                    for trait, badge in trait_badges_map.items()
                                    if trait in u["traits"]
                                }
                            )
                        )
                        if trait_badges_map
                        else [],
                        **(
                            dict(
                                moderation_state=u["moderation_state"],
                                token_id=u["token_id"],
                            )
                            if include_admin_info
                            else {}
                        ),
                    )
                    for u in p.object_list
                ),
                key=lambda u: (
                    u["profile"]["display_name"].lower(),
                    int(u["inactive"] or 0),
                ),
            ),
            "isLastPage": not p.has_next(),
        }
    except InvalidPage:
        return {
            "results": [],
            "isLastPage": True,
        }


async def user_broadcast(event_type, data, user_id, socket_id):
    await get_channel_layer().group_send(
        GROUP_USER.format(id=user_id),
        {
            "type": "user.broadcast",
            "event_type": event_type,
            "data": data,
            "socket": socket_id,
        },
    )
