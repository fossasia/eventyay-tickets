import uuid

from django.db import models


def default_text():
    return []


class Exhibitor(models.Model):
    class Sizes(models.TextChoices):
        S = "1x1"
        M = "3x1"
        L = "3x3"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=80, null=True)
    tagline = models.CharField(max_length=250, null=True)
    short_text = models.TextField(max_length=500, null=True)
    logo = models.URLField(null=True, blank=True)
    banner_list = models.URLField(null=True, blank=True)
    banner_detail = models.URLField(null=True, blank=True)
    contact_enabled = models.BooleanField(default=True)
    text_legacy = models.TextField(null=True)
    text_content = models.JSONField(default=default_text)
    size = models.CharField(max_length=3, default=Sizes.S, choices=Sizes.choices)
    sorting_priority = models.IntegerField(default=0)
    room = models.ForeignKey(
        to="Room",
        related_name="exhibitors",
        on_delete=models.CASCADE,
    )
    world = models.ForeignKey(
        to="World",
        related_name="exhibitors",
        on_delete=models.CASCADE,
    )
    highlighted_room = models.ForeignKey(
        to="Room",
        related_name="highlighted_by_exhibitors",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    def serialize(self):
        links = list(
            self.links.order_by("display_text").values(
                "display_text", "url", "category", "sorting_priority"
            )
        )
        social_media_links = list(
            self.social_media_links.order_by("display_text").values(
                "display_text", "url"
            )
        )
        staff = []
        for staff_member in self.staff.order_by("id").all():
            staff.append(
                staff_member.user.serialize_public(
                    trait_badges_map=self.world.config.get("trait_badges_map")
                )
            )

        return dict(
            id=str(self.id),
            name=self.name,
            tagline=self.tagline,
            logo=self.logo,
            banner_list=self.banner_list,
            banner_detail=self.banner_detail,
            contact_enabled=self.contact_enabled,
            text_legacy=self.text_legacy,
            text_content=self.text_content,
            short_text=self.short_text,
            size=self.size,
            sorting_priority=self.sorting_priority,
            links=links,
            social_media_links=social_media_links,
            staff=staff,
            room_id=str(self.room_id),
            highlighted_room_id=str(self.highlighted_room_id)
            if self.highlighted_room_id
            else None,
        )

    def serialize_short(self):
        return dict(
            id=str(self.id),
            name=self.name,
        )

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        self.room.touch()
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        self.room.touch()
        return r


class ExhibitorSocialMediaLink(models.Model):
    exhibitor = models.ForeignKey(
        to=Exhibitor,
        db_index=True,
        related_name="social_media_links",
        on_delete=models.CASCADE,
    )
    display_text = models.CharField(max_length=300, blank=False)
    url = models.URLField(blank=False)


class ExhibitorLink(models.Model):
    class Category(models.TextChoices):
        PROFILE = "profile"
        DOWNLOAD = "download"

    exhibitor = models.ForeignKey(
        to=Exhibitor,
        db_index=True,
        related_name="links",
        on_delete=models.CASCADE,
    )
    category = models.CharField(
        max_length=32, default=Category.PROFILE, choices=Category.choices
    )
    display_text = models.CharField(max_length=300, blank=False)
    url = models.URLField(blank=False)
    sorting_priority = models.IntegerField(default=0)


class ExhibitorStaff(models.Model):
    exhibitor = models.ForeignKey(
        to=Exhibitor,
        db_index=True,
        related_name="staff",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exhibitor_staff",
    )

    class Meta:
        unique_together = (("user", "exhibitor"),)

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        self.user.touch()
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        self.user.touch()
        return r


class ContactRequest(models.Model):
    class States(models.TextChoices):
        OPEN = "open"
        MISSED = "missed"
        ANSWERED = "answered"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    exhibitor = models.ForeignKey(
        to=Exhibitor,
        db_index=True,
        related_name="contact_requests",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exhibitor_contact_requests",
    )
    state = models.CharField(max_length=8, default=States.OPEN, choices=States.choices)
    answered_by = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exhibitor_answered_contact_requests",
    )
    timestamp = models.DateTimeField(auto_now_add=True, null=True)

    def serialize(self):
        return dict(
            id=str(self.id),
            exhibitor=self.exhibitor.serialize_short(),
            user=self.user.serialize_public() if self.user else None,
            state=self.state,
            answered_by=self.answered_by.serialize_public()
            if self.answered_by
            else None,
            timestamp=self.timestamp.isoformat() if self.timestamp else None,
        )


class ExhibitorView(models.Model):
    exhibitor = models.ForeignKey(
        to="Exhibitor", related_name="views", on_delete=models.CASCADE
    )
    datetime = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        to="user", related_name="exhibitor_views", on_delete=models.CASCADE
    )
