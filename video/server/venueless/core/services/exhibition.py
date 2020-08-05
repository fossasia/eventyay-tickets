from channels.db import database_sync_to_async

from venueless.core.models import ContactRequest, Exhibitor, ExhibitorStaff
from venueless.core.services.user import get_user_by_id


def get_exhibitor_by_id(world_id, id):
    try:
        return Exhibitor.objects.get(id=id, world_id=world_id)
    except Exhibitor.DoesNotExist:
        return


def get_request_by_id(world_id, id):
    try:
        return ContactRequest.objects.get(id=id, exhibitor__world_id=world_id)
    except ContactRequest.DoesNotExist:
        return


class ExhibitionService:
    def __init__(self, world_id):
        self.world_id = world_id

    @database_sync_to_async
    def get_exhibitors(self, room_id):
        qs = (
            Exhibitor.objects.filter(world__id=self.world_id)
            .filter(room__id=room_id)
            .order_by("sorting_priority", "name")
        )

        return [
            dict(
                id=str(e["id"]),
                name=e["name"],
                tagline=e["tagline"],
                short_text=e["short_text"],
                logo=e["logo"],
                size=e["size"],
                sorting_priority=e["sorting_priority"],
            )
            for e in qs.values(
                "id",
                "name",
                "tagline",
                "short_text",
                "logo",
                "size",
                "sorting_priority",
            )
        ]

    @database_sync_to_async
    def get_exhibitor(self, exhibitor_id):
        e = get_exhibitor_by_id(self.world_id, exhibitor_id)
        if not e:
            return None

        links = list(e.links.values("display_text", "url"))
        social_media_links = list(e.social_media_links.values("display_text", "url"))
        staff = list(e.staff.values_list("user__id", flat=True))

        return dict(
            id=str(e.id),
            name=e.name,
            tagline=e.tagline,
            logo=e.logo,
            text=e.text,
            size=e.size,
            sorting_priority=e.sorting_priority,
            links=links,
            social_media_links=social_media_links,
            staff=staff,
        )

    @database_sync_to_async
    def contact(self, exhibitor_id, user):
        e = get_exhibitor_by_id(self.world_id, exhibitor_id)
        if not e:
            return None
        request = ContactRequest.objects.create(exhibitor=e, user=user,)
        request = dict(
            id=str(request.id),
            exhibitor_id=str(request.exhibitor.id),
            user_id=str(request.user.id),
            state=request.state,
        )
        return request

    @database_sync_to_async
    def missed(self, contact_request_id):
        r = get_request_by_id(self.world_id, contact_request_id)
        if not r:
            return None
        r.state = "missed"
        return r.save(update_fields=["state"])

    @database_sync_to_async
    def accept(self, contact_request_id):
        r = get_request_by_id(self.world_id, contact_request_id)
        if not r:
            return None
        if r.state == "answered":
            return None
        r.state = "answered"
        r.save(update_fields=["state"])
        r = dict(
            id=str(r.id),
            exhibitor_id=str(r.exhibitor.id),
            user_id=str(r.user.id),
            state=r.state,
        )
        return r

    @database_sync_to_async
    def add_staff(self, exhibitor_id, user_id):
        e = get_exhibitor_by_id(self.world_id, exhibitor_id)
        if not e:
            return None
        u = get_user_by_id(self.world_id, user_id)
        if not u:
            return None

        return ExhibitorStaff.objects.create(user=u, exhibitor=e,)

    @database_sync_to_async
    def get_staff(self, exhibitor_id):
        e = get_exhibitor_by_id(self.world_id, exhibitor_id)
        if not e:
            return None
        return list(e.staff.values_list("user__id", flat=True))
