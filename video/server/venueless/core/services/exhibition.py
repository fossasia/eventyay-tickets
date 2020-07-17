from channels.db import database_sync_to_async

from venueless.core.models import Exhibitor


def get_exhibitor_by_id(world_id, id):
    try:
        return Exhibitor.objects.select_related("social_media_links", "links").get(
            id=id, world_id=world_id
        )
    except Exhibitor.DoesNotExist:
        return


class ExhibitionService:
    def __init__(self, world_id):
        self.world_id = world_id

    @database_sync_to_async
    def get_exhibitors(self, room_id):
        qs = Exhibitor.objects.filter(world__id=self.world_id).filter(room__id=room_id)

        return [
            dict(
                id=str(e["id"]),
                name=e["name"],
                description=e["description"],
                logo=e["logo"],
                size=e["size"],
                sorting_priority=e["sorting_priority"],
            )
            for e in qs.values(
                "id", "name", "description", "logo", "size", "sorting_priority"
            )
        ]

    @database_sync_to_async
    def get_exhibitor(self, id):
        e = get_exhibitor_by_id(self.world_id, id)
        if not e:
            return None

        links = e.links.values("display_text", "url")
        social_media_links = e.social_media_links.values("display_text", "url")

        return dict(
            id=str(e.id),
            name=e.name,
            description=e.description,
            logo=e.logo.url,
            text=e.text,
            header_img=e.header_img.url,
            size=e.size,
            sorting_priority=e.sorting_priority,
            links=links,
            social_media_links=social_media_links,
        )
