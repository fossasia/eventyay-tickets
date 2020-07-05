import copy

from django.db import transaction

from venueless.core.models import Channel, Room, World


@transaction.atomic
def import_config(data):
    data = copy.deepcopy(data)
    world_config = data.pop("world")
    world, _ = World.objects.get_or_create(id=world_config.pop("id"))
    world.title = world_config.pop("title")
    world.config = world_config
    world.trait_grants = data.pop("trait_grants", {})
    world.roles = data.pop("roles", {})
    world.save()

    for i, room_config in enumerate(data.pop("rooms")):
        room, _ = Room.objects.get_or_create(
            import_id=room_config.pop("id"),
            world=world,
            defaults={"name": room_config["name"]},
        )
        room.name = room_config.pop("name")
        room.description = room_config.pop("description")
        room_config.pop("picture")  # TODO import picure from path or http
        room.trait_grants = room_config.pop("trait_grants", {})
        room.module_config = room_config.pop("modules")
        room.pretalx_id = room_config.pop("pretalx_id", 0)
        room.sorting_priority = i
        room.save()
        assert not room_config, f"Unused config data: {room_config}"

        for module in room.module_config:
            if module["type"] == "chat.native":
                Channel.objects.get_or_create(room=room, world=world)

    assert not data, f"Unused config data: {data}"
