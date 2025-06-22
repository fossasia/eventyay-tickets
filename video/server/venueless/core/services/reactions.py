from channels.db import database_sync_to_async

from venueless.core.models.room import Reaction


@database_sync_to_async
def store_reaction(room_id: str, reaction: str, amount: int):
    Reaction.objects.create(room_id=room_id, reaction=reaction, amount=amount)
