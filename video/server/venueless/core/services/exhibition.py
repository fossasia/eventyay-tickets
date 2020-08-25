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


def get_staff_by_id(exhibitor_id, user_id):
    try:
        return ExhibitorStaff.objects.get(exhibitor__id=exhibitor_id, user__id=user_id)
    except ExhibitorStaff.DoesNotExist:
        return


class ExhibitionService:
    def __init__(self, world_id):
        self.world_id = world_id

    @database_sync_to_async
    def get_all_exhibitors(self):
        qs = Exhibitor.objects.filter(world__id=self.world_id).order_by("name")

        return [
            dict(id=str(e["id"]), name=e["name"],) for e in qs.values("id", "name",)
        ]

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
                banner_list=e["banner_list"],
                size=e["size"],
                sorting_priority=e["sorting_priority"],
            )
            for e in qs.values(
                "id",
                "name",
                "tagline",
                "short_text",
                "banner_list",
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
        return e.serialize()

    @database_sync_to_async
    def contact(self, exhibitor_id, user):
        e = get_exhibitor_by_id(self.world_id, exhibitor_id)
        if not e:
            return None
        request = ContactRequest.objects.create(exhibitor=e, user=user,)
        return request.serialize()

    @database_sync_to_async
    def missed(self, contact_request_id):
        r = get_request_by_id(self.world_id, contact_request_id)
        if not r:
            return None
        r.state = "missed"
        r.save(update_fields=["state"])
        return r.serialize()

    @database_sync_to_async
    def accept(self, contact_request_id, staff):
        r = get_request_by_id(self.world_id, contact_request_id)
        if not r:
            return None
        if r.state == "answered":
            return None
        r.state = "answered"
        r.answered_by = staff
        r.save(update_fields=["state", "answered_by"])
        return r.serialize()

    @database_sync_to_async
    def add_staff(self, exhibitor_id, user_id):
        e = get_exhibitor_by_id(self.world_id, exhibitor_id)
        if not e:
            return None
        u = get_user_by_id(self.world_id, user_id)
        if not u:
            return None
        try:
            s = ExhibitorStaff.objects.get(user=u, exhibitor=e,)
        except ExhibitorStaff.DoesNotExist:
            s = ExhibitorStaff.objects.create(user=u, exhibitor=e,)
        return s

    @database_sync_to_async
    def remove_staff(self, exhibitor_id, user_id):
        s = get_staff_by_id(exhibitor_id, user_id)
        if not s:
            return None
        return s.delete()

    @database_sync_to_async
    def get_staff(self, exhibitor_id):
        e = get_exhibitor_by_id(self.world_id, exhibitor_id)
        if not e:
            return None
        return list(e.staff.values_list("user__id", flat=True))

    @database_sync_to_async
    def get_open_requests_from_user(self, user):
        return [
            cr.serialize()
            for cr in user.exhibitor_contact_requests.filter(state="open")
        ]

    def get_exhibition_data_for_user(self, user):
        exhibitors = Exhibitor.objects.filter(
            world__id=self.world_id, staff__user=user,
        )
        contact_requests = ContactRequest.objects.filter(exhibitor__in=exhibitors)
        return {
            "exhibitors": [ex.serialize_short() for ex in exhibitors],
            "contact_requests": [cr.serialize() for cr in contact_requests],
        }
