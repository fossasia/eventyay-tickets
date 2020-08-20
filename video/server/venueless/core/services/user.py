from collections import namedtuple

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.db.transaction import atomic

from ...live.channels import GROUP_USER
from ..models.auth import User
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
def get_public_user(world_id, id, include_admin_info=False):
    user = get_user_by_id(world_id, id)
    if not user:
        return None
    return user.serialize_public(include_admin_info=include_admin_info)


@database_sync_to_async
def get_public_users(world_id, *, ids=None, include_admin_info=False):
    # This method is called a lot, especially when lots of people join at once (event start, server reboot, …)
    # For performance reasons, we therefore do not initialize model instances and use serialize_public()
    if ids is not None:
        qs = User.objects.filter(id__in=ids, world_id=world_id)
    else:
        qs = User.objects.filter(world_id=world_id).order_by(
            "profile__display_name", "id"
        )
    return [
        dict(
            id=str(u["id"]),
            profile=u["profile"],
            **(
                {"moderation_state": u["moderation_state"]}
                if include_admin_info
                else {}
            ),
        )
        for u in qs.values("id", "profile", "moderation_state")
    ]


def get_user(
    world_id=None, *, with_id=None, with_token=None, with_client_id=None,
):
    if with_id:
        user = get_user_by_id(world_id, with_id)
        return user

    token_id = None
    if with_token:
        token_id = with_token["uid"]
        user = get_user_by_token_id(world_id, token_id)
    elif with_client_id:
        user = get_user_by_client_id(world_id, with_client_id)
    else:
        raise Exception(
            "get_user was called without valid with_token, with_id or with_client_id"
        )

    if user:
        if with_token and (user.traits != with_token.get("traits")):
            traits = with_token["traits"]
            update_user(world_id, id=user.id, traits=traits)
        return user

    if token_id:
        user = create_user(
            world_id=world_id,
            token_id=token_id,
            profile=with_token.get("profile") if with_token else None,
            traits=with_token.get("traits") if with_token else None,
        )
    else:
        user = create_user(
            world_id=world_id,
            client_id=with_client_id,
            traits=with_token.get("traits") if with_token else None,
        )
    return user


def create_user(world_id, *, token_id=None, client_id=None, traits=None, profile=None):
    return User.objects.create(
        world_id=world_id,
        token_id=token_id,
        client_id=client_id,
        traits=traits or [],
        profile=profile or {},
    )


@atomic
def update_user(world_id, id, *, traits=None, public_data=None, serialize=True):
    # TODO: Exception handling
    user = User.objects.select_for_update().get(id=id, world_id=world_id)

    if traits is not None:
        user.traits = traits
        user.save(update_fields=["traits"])

    if public_data is not None:
        save_fields = []
        if "profile" in public_data and public_data["profile"] != user.profile:
            # TODO: Anything we want to validate here?
            user.profile = public_data.get("profile")
            save_fields.append("profile")
        if save_fields:
            user.save(update_fields=save_fields)

    return user.serialize_public() if serialize else user


LoginResult = namedtuple("LoginResult", "user world_config chat_channels")


def login(*, world=None, token=None, client_id=None,) -> LoginResult:
    from .chat import ChatService
    from .world import get_world_config_for_user

    user = get_user(world_id=world.pk, with_client_id=client_id, with_token=token)

    if (
        not user
        or user.is_banned
        or not world.has_permission(user=user, permission=Permission.WORLD_VIEW)
    ):
        return

    return LoginResult(
        user=user,
        world_config=get_world_config_for_user(world, user),
        chat_channels=ChatService(world).get_channels_for_user(
            user.pk, is_volatile=False
        ),
    )


@database_sync_to_async
@atomic
def get_blocked_users(user) -> bool:
    return [u.serialize_public() for u in user.blocked_users.all()]


@database_sync_to_async
@atomic
def set_user_banned(world, user_id) -> bool:
    user = get_user_by_id(world_id=world.pk, user_id=user_id)
    if not user:
        return False
    user.moderation_state = User.ModerationState.BANNED
    user.save(update_fields=["moderation_state"])
    return True


@database_sync_to_async
@atomic
def set_user_silenced(world, user_id) -> bool:
    user = get_user_by_id(world_id=world.pk, user_id=user_id)
    if not user:
        return False
    if user.moderation_state == User.ModerationState.BANNED:
        return True
    user.moderation_state = User.ModerationState.SILENCED
    user.save(update_fields=["moderation_state"])
    return True


@database_sync_to_async
@atomic
def set_user_free(world, user_id) -> bool:
    user = get_user_by_id(world_id=world.pk, user_id=user_id)
    if not user:
        return False
    user.moderation_state = User.ModerationState.NONE
    user.save(update_fields=["moderation_state"])
    return True


@database_sync_to_async
@atomic
def block_user(world, blocking_user: User, blocked_user_id) -> bool:
    blocked_user = get_user_by_id(world_id=world.pk, user_id=blocked_user_id)
    if not blocked_user:
        return False

    blocking_user.blocked_users.add(blocked_user)
    blocked_user.touch()
    return True


@database_sync_to_async
@atomic
def unblock_user(world, blocking_user: User, blocked_user_id) -> bool:
    blocked_user = get_user_by_id(world_id=world.pk, user_id=blocked_user_id)
    if not blocked_user:
        return False

    blocking_user.blocked_users.remove(blocked_user)
    blocked_user.touch()
    return True


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
