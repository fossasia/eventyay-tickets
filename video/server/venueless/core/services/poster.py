from channels.db import database_sync_to_async
from django.db.transaction import atomic

from venueless.core.models import (
    AuditLog,
    Channel,
    Poster,
    PosterLink,
    PosterPresenter,
    PosterVote,
    Room,
)
from venueless.core.services.user import get_user_by_id


def get_poster_by_id(world_id, id):
    try:
        return Poster.objects.prefetch_related("links", "votes", "presenters").get(
            id=id, world_id=world_id
        )
    except Poster.DoesNotExist:
        return


def get_presenter_by_id(poster_id, user_id):
    try:
        return PosterPresenter.objects.get(poster__id=poster_id, user__id=user_id)
    except PosterPresenter.DoesNotExist:
        return


def get_or_create_link(link, poster):
    obj, _ = PosterLink.objects.get_or_create(
        poster=poster,
        display_text=link["display_text"],
        url=link["url"],
        sorting_priority=link["sorting_priority"],
        defaults=dict(
            poster=poster,
            display_text=link["display_text"],
            url=link["url"],
            sorting_priority=link["sorting_priority"],
        ),
    )
    return obj


def get_or_create_presenter(user, poster):
    obj, _ = PosterPresenter.objects.get_or_create(
        poster=poster,
        user__id=user.id,
        defaults=dict(
            poster=poster,
            user=user,
        ),
    )
    return obj


def get_room_by_id(world_id, id):
    try:
        return Room.objects.get(id=id, world__id=world_id)
    except Room.DoesNotExist:
        return


class PosterService:
    def __init__(self, world):
        self.world = world

    @database_sync_to_async
    def get_all_posters(self, presenter_includes_user=None):
        qs = Poster.objects.filter(world__id=self.world.pk).order_by("title")

        if presenter_includes_user:
            qs = qs.filter(
                presenters__user=presenter_includes_user,
            )

        return [
            dict(
                id=str(e["id"]),
                title=e["title"],
            )
            for e in qs.values(
                "id",
                "title",
            )
        ]

    @database_sync_to_async
    def get_posters(self, room_id, user=None):
        qs = (
            Poster.objects.filter(world__id=self.world.pk)
            .filter(parent_room__id=room_id)
            .order_by("title")
        ).prefetch_related("links", "votes", "presenters")

        return [p.serialize(user) for p in qs]

    @database_sync_to_async
    def get_poster(self, poster_id, user=None):
        poster = get_poster_by_id(self.world.pk, poster_id)
        if not poster:
            return None
        return poster.serialize(user)

    @database_sync_to_async
    @atomic
    def delete(self, poster_id, by_user):
        poster = get_poster_by_id(self.world.pk, poster_id)
        if not poster:
            return None
        AuditLog.objects.create(
            world_id=self.world.pk,
            user=by_user,
            type="poster.deleted",
            data={
                "object": poster_id,
                "old": poster.serialize(),
            },
        )
        return poster.delete()

    @database_sync_to_async
    @atomic
    def patch(self, data, world, by_user, exclude_fields=tuple()):
        is_creating = False
        old = {}
        if data["id"] == "":
            is_creating = True
            poster = Poster(world=world)
        else:
            poster = get_poster_by_id(self.world.pk, data["id"])
            old = poster.serialize()
            if not poster:
                return None

        for room_type in ("parent_room", "presentation_room"):
            id_attr = f"{room_type}_id"
            if id_attr in data:
                room_id = data.get(id_attr)
                room = (
                    get_room_by_id(
                        self.world.pk,
                        room_id or getattr(poster, id_attr, None),
                    )
                    if room_id
                    else None
                )
                if not room and room_type == "parent_room":
                    return None
                elif room_type not in exclude_fields and id_attr not in exclude_fields:
                    setattr(poster, room_type, room)

        allowed_keys = (
            "title",
            "abstract",
            "authors",
            "tags",
            "category",
            "poster_url",
            "poster_preview",
            "schedule_session",
        )
        for key, value in data.items():
            if key in allowed_keys and key not in exclude_fields:
                setattr(poster, key, value)

        if is_creating:
            poster.channel = Channel.objects.create(world=poster.world)
        poster.save()

        if "links" in data and "links" not in exclude_fields:
            links = []
            for link in data["links"]:
                links.append(get_or_create_link(link, poster))
            for link in poster.links.all():
                if link not in links:
                    link.delete()

        if "presenters" in data and "presenters" not in exclude_fields:
            presenters = []
            for user in data["presenters"]:
                user = get_user_by_id(self.world.pk, user["id"])
                presenters.append(get_or_create_presenter(user, poster))
            for presenter in poster.presenters.all():
                if presenter not in presenters:
                    presenter.delete()

        new = poster.serialize()
        AuditLog.objects.create(
            world_id=self.world.pk,
            user=by_user,
            type="poster.updated",
            data={
                "object": str(poster.id),
                "old": old,
                "new": new,
            },
        )

        return new

    @database_sync_to_async
    def vote(self, poster_id, user):
        poster = get_poster_by_id(self.world.pk, poster_id)
        if not poster:
            return None
        vote, created = PosterVote.objects.get_or_create(user=user, poster=poster)
        return {
            "poster": poster_id,
            "user": str(user.id),
            "datetime": vote.datetime.isoformat(),
        }

    @database_sync_to_async
    def unvote(self, poster_id, user):
        poster = get_poster_by_id(self.world.pk, poster_id)
        if not poster:
            return None
        return PosterVote.objects.filter(user=user, poster=poster).delete()

    @database_sync_to_async
    def get_presenters(self, poster_id):
        poster = get_poster_by_id(self.world.pk, poster_id)
        if not poster:
            return None
        return list(poster.presenters.values_list("user__id", flat=True))

    @database_sync_to_async
    def get_posters_presented_by_user(self, user_id):
        posters = Poster.objects.filter(
            world__id=self.world.pk,
            presenters__user__id=user_id,
        ).prefetch_related("links", "votes", "presenters")
        return [poster.serialize() for poster in posters]
