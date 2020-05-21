import pytest
from channels.db import database_sync_to_async

from venueless.core.models import User
from venueless.core.permissions import Permission


@pytest.mark.django_db
def test_user_explicit_roles(world, chat_room, bbb_room):
    user = User.objects.create(world=world, profile={}, traits=[])
    assert user.get_role_grants() == set()
    assert not world.has_permission(
        user=user, permission=Permission.WORLD_ROOMS_CREATE_CHAT
    )
    assert world.get_all_permissions(user)[world] == {"world:view"}
    assert world.get_all_permissions(user)[chat_room] == {
        "room:bbb.join",
        "room:chat.join",
        "room:chat.read",
        "room:chat.send",
        "room:view",
        "world:view",
    }

    user.world_grants.create(role="room_creator", world=world)
    user.refresh_from_db()
    assert user.get_role_grants() == {"room_creator"}
    assert world.has_permission(
        user=user, permission=Permission.WORLD_ROOMS_CREATE_CHAT
    )
    assert not world.has_permission(user=user, permission=Permission.WORLD_UPDATE)

    user.refresh_from_db()
    assert user.get_role_grants(chat_room) == {"room_creator"}
    assert not world.has_permission(
        user=user, permission=Permission.ROOM_INVITE, room=chat_room
    )
    assert world.get_all_permissions(user)[world] == {
        "world:view",
        "world:rooms.create.chat",
    }

    user.room_grants.create(role="room_owner", room=chat_room, world=world)
    user.refresh_from_db()
    assert user.get_role_grants(chat_room) == {"room_creator", "room_owner"}
    assert world.has_permission(
        user=user, permission=Permission.ROOM_INVITE, room=chat_room
    )
    assert world.get_all_permissions(user)[chat_room] == {
        "room:bbb.join",
        "room:chat.join",
        "room:chat.read",
        "room:chat.send",
        "room:invite",
        "room:update",
        "room:delete",
        "room:view",
        "world:view",
    }
    assert world.get_all_permissions(user)[bbb_room] == {
        "room:bbb.join",
        "room:chat.join",
        "room:chat.read",
        "room:chat.send",
        "room:view",
        "world:view",
    }


@pytest.mark.django_db
def test_user_implicit_roles(world, chat_room, bbb_room):
    user = User.objects.create(world=world, profile={}, traits=["trait123", "trait456"])
    assert user.get_role_grants() == set()
    assert not world.has_permission(
        user=user, permission=Permission.WORLD_ROOMS_CREATE_CHAT
    )
    assert world.get_all_permissions(user)[world] == {"world:view"}
    assert world.get_all_permissions(user)[chat_room] == {
        "room:bbb.join",
        "room:chat.join",
        "room:chat.read",
        "room:chat.send",
        "room:view",
        "world:view",
    }

    world.trait_grants["room_creator"] = ["trait123", "trait789"]
    world.save()
    assert not world.has_permission(
        user=user, permission=Permission.WORLD_ROOMS_CREATE_CHAT
    )

    world.trait_grants["room_creator"] = ["trait123"]
    world.save()
    assert world.has_permission(
        user=user, permission=Permission.WORLD_ROOMS_CREATE_CHAT
    )
    assert not world.has_permission(user=user, permission=Permission.WORLD_UPDATE)
    assert world.get_all_permissions(user)[world] == {
        "world:view",
        "world:rooms.create.chat",
    }

    assert not world.has_permission(
        user=user, permission=Permission.ROOM_INVITE, room=chat_room
    )

    chat_room.trait_grants["room_owner"] = ["trait123", "trait789"]
    chat_room.save()
    assert not world.has_permission(
        user=user, permission=Permission.ROOM_INVITE, room=chat_room
    )

    chat_room.trait_grants["room_owner"] = ["trait123", "trait456"]
    chat_room.save()
    assert world.has_permission(
        user=user, permission=Permission.ROOM_INVITE, room=chat_room
    )
    assert not world.has_permission(
        user=user, permission=Permission.ROOM_CHAT_MODERATE, room=chat_room
    )
    assert world.get_all_permissions(user)[chat_room] == {
        "room:bbb.join",
        "room:chat.join",
        "room:chat.read",
        "room:chat.send",
        "room:invite",
        "room:update",
        "room:delete",
        "room:view",
        "world:view",
    }
    assert world.get_all_permissions(user)[bbb_room] == {
        "room:bbb.join",
        "room:chat.join",
        "room:chat.read",
        "room:chat.send",
        "room:view",
        "world:view",
    }


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_check_async(world, chat_room, bbb_room):
    user = await database_sync_to_async(User.objects.create)(
        world=world, profile={}, traits=["trait123", "trait456"]
    )
    assert not await world.has_permission_async(
        user=user, permission=Permission.WORLD_ROOMS_CREATE_CHAT
    )

    world.trait_grants["room_creator"] = ["trait123", "trait789"]
    await database_sync_to_async(world.save)()
    assert not await world.has_permission_async(
        user=user, permission=Permission.WORLD_ROOMS_CREATE_CHAT
    )

    world.trait_grants["room_creator"] = ["trait123"]
    await database_sync_to_async(world.save)()
    assert await world.has_permission_async(
        user=user, permission=Permission.WORLD_ROOMS_CREATE_CHAT
    )
    assert not await world.has_permission_async(
        user=user, permission=Permission.WORLD_UPDATE
    )
    assert not await world.has_permission_async(
        user=user, permission=Permission.ROOM_INVITE, room=chat_room
    )
