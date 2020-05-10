from channels.db import database_sync_to_async
from django.db.transaction import atomic

from ..models.auth import User


@database_sync_to_async
def get_user_by_id(world_id, user_id):
    try:
        return User.objects.get(id=user_id, world_id=world_id)
    except User.DoesNotExist:
        return


@database_sync_to_async
def get_user_by_token_id(world_id, token_id):
    try:
        return User.objects.get(token_id=token_id, world_id=world_id)
    except User.DoesNotExist:
        return


@database_sync_to_async
def get_user_by_client_id(world_id, client_id):
    try:
        return User.objects.get(client_id=client_id, world_id=world_id)
    except User.DoesNotExist:
        return


async def get_public_user(world_id, id):
    user = await get_user_by_id(world_id, id)
    if not user:
        return None
    return user.serialize_public()


@database_sync_to_async
def get_public_users(world_id, ids):
    # This method is called a lot, especially when lots of people join at once (event start, server reboot, …)
    # For performance reasons, we therefore do not initialize model instances and use serialize_public()
    return [
        {"id": str(u["id"]), "profile": u["profile"]}
        for u in User.objects.filter(id__in=ids, world_id=world_id).values(
            "id", "profile"
        )
    ]


async def get_user(
    world_id=None,
    *,
    with_id=None,
    with_token=None,
    with_client_id=None,
    serialize=True,
):
    if with_id:
        user = await get_user_by_id(world_id, with_id)
        return user.serialize_public() if serialize and user else user

    token_id = None
    if with_token:
        token_id = with_token["uid"]
        user = await get_user_by_token_id(world_id, token_id)
    elif with_client_id:
        user = await get_user_by_client_id(world_id, with_client_id)
    else:
        raise Exception(
            "get_user was called without valid with_token, with_id or with_client_id"
        )

    if user:
        traits = None
        if with_token and (user.traits != with_token.get("traits")):
            traits = with_token["traits"]
        await update_user(world_id, id=user.id, traits=traits)
        return user.serialize_public() if serialize else user

    if token_id:
        user = await create_user(
            world_id=world_id,
            token_id=token_id,
            traits=with_token.get("traits") if with_token else None,
        )
    else:
        user = await create_user(
            world_id=world_id,
            client_id=with_client_id,
            traits=with_token.get("traits") if with_token else None,
        )
    return user.serialize_public() if serialize and user else user


@database_sync_to_async
def create_user(world_id, *, token_id=None, client_id=None, traits=None, profile=None):
    return User.objects.create(
        world_id=world_id,
        token_id=token_id,
        client_id=client_id,
        traits=traits or [],
        profile=profile or {},
    )


@database_sync_to_async
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
