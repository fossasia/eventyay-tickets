import uuid

from django.db import models


def default_text():
    return []


class Poster(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    import_id = models.TextField(null=True, blank=True, db_index=True)
    title = models.TextField(null=True)
    abstract = models.JSONField(default=default_text)
    authors = models.JSONField(default=default_text)
    tags = models.JSONField(default=default_text)
    category = models.TextField(null=True, blank=True)

    poster_url = models.URLField(null=True, blank=True)  # TODO file upload
    poster_preview = models.URLField(null=True, blank=True)  # TODO file upload
    schedule_session = models.TextField(null=True, blank=True)

    world = models.ForeignKey(
        to="World",
        related_name="posters",
        on_delete=models.CASCADE,
    )
    parent_room = models.ForeignKey(
        to="Room",
        related_name="child_posters",
        on_delete=models.CASCADE,
    )
    presentation_room = models.ForeignKey(
        to="Room",
        related_name="presentation_posters",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    channel = models.ForeignKey(
        to="Channel",
        related_name="posters",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    def serialize(self, user=None):
        presenters = []
        for presenter in self.presenters.order_by("id").all():
            presenters.append(
                presenter.user.serialize_public(
                    trait_badges_map=self.world.config.get("trait_badges_map")
                )
            )
        links = list(
            self.links.order_by("display_text").values(
                "display_text", "url", "sorting_priority"
            )
        )
        votes = self.votes.all().count()

        result = dict(
            id=str(self.id),
            title=self.title,
            abstract=self.abstract,
            authors=self.authors,
            category=self.category,
            tags=self.tags,
            poster_url=self.poster_url,
            poster_preview=self.poster_preview,
            schedule_session=self.schedule_session,
            presenters=presenters,
            votes=votes,
            links=links,
            parent_room_id=str(self.parent_room_id),
            channel=str(self.channel_id) if getattr(self, "channel_id", None) else None,
            presentation_room_id=str(self.presentation_room_id)
            if getattr(self, "presentation_room_id", None)
            else None,
        )
        if user:
            result["has_voted"] = self.votes.filter(user=user).exists()
        return result

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        self.parent_room.touch()
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        self.parent_room.touch()
        return r


class PosterPresenter(models.Model):
    poster = models.ForeignKey(
        to=Poster,
        db_index=True,
        related_name="presenters",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="poster_presenter",
    )

    class Meta:
        unique_together = (("user", "poster"),)

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        self.user.touch()
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        self.user.touch()
        return r


class PosterVote(models.Model):
    poster = models.ForeignKey(
        to="Poster", related_name="votes", on_delete=models.CASCADE
    )
    datetime = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        to="user", related_name="poster_votes", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = (("user", "poster"),)


class PosterLink(models.Model):
    poster = models.ForeignKey(
        to=Poster,
        db_index=True,
        related_name="links",
        on_delete=models.CASCADE,
    )
    display_text = models.CharField(max_length=300, blank=False)
    url = models.URLField(blank=False)
    sorting_priority = models.IntegerField(default=0)
