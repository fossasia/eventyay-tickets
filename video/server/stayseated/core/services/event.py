import json
import os

from aiofile import AIOFile

from ...settings import BASE_DIR


async def get_event_config(event_name):
    try:
        async with AIOFile(
            os.path.join(BASE_DIR, "sample", "events", event_name + ".json"),
            "r",
            encoding="utf-8",
        ) as afp:
            data = json.loads(await afp.read())
    except OSError:
        return None

    return data


async def get_event_config_for_user(event_name, user):
    event = await get_event_config(event_name)

    # TODO: Check if user has access to this event
    # TODO: Remove any rooms the user should not see

    event["event"].pop("JWT_secrets", None)
    return event


async def get_room_config(event_name, room_id):
    event = await get_event_config(event_name)
    for r in event["rooms"]:
        if r["id"] == room_id:
            return r
