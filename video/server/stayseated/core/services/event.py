import json
import os

from aiofile import AIOFile

from ...settings import BASE_DIR


async def get_event_config(event_name):
    try:
        async with AIOFile(os.path.join(BASE_DIR, 'sample', 'events', event_name + '.json'), 'r', encoding='utf-8') as \
                afp:
            data = json.loads(await afp.read())
    except OSError:
        return None

    # TODO: Check if user has access to this event
    # TODO: Remove any rooms the user should not see

    return data
