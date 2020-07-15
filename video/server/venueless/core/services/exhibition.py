from channels.db import database_sync_to_async

from venueless.core.models import Exhibitor


class ExhibitionService:
    def __init__(self, world_id):
        self.world_id = world_id

    @database_sync_to_async
    def get_exhibitors(self, room_id=None):
        qs = Exhibitor.objects.filter(world__id=self.world_id)
        if room_id:
            qs.filter(room__id=room_id)

        return [
            dict(
                id=str(e["id"]),
                name=e["name"],
                description=e["description"],
                grid_color=e["grid_color"],
            )
            for e in qs.values("id", "name", "description", "grid_color")
        ]
