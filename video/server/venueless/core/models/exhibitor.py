import uuid

from django.db import models


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
    text = models.TextField(null=True)
    size = models.CharField(max_length=3, default=Sizes.S, choices=Sizes.choices)
    sorting_priority = models.IntegerField(default=0)
    room = models.ForeignKey(
        to="Room", related_name="exhibitors", on_delete=models.CASCADE,
    )
    world = models.ForeignKey(
        to="World", related_name="exhibitors", on_delete=models.CASCADE,
    )

    def serialize(self):
        links = list(
            self.links.order_by("display_text").values(
                "display_text", "url", "category"
            )
        )
        social_media_links = list(
            self.social_media_links.order_by("display_text").values(
                "display_text", "url"
            )
        )
        staff = []
        for staff_member in self.staff.order_by("id").all():
            staff.append(staff_member.user.serialize_public())

        return dict(
            id=str(self.id),
            name=self.name,
            tagline=self.tagline,
            logo=self.logo,
            banner_list=self.banner_list,
            banner_detail=self.banner_detail,
            contact_enabled=self.contact_enabled,
            text=self.text,
            size=self.size,
            sorting_priority=self.sorting_priority,
            links=links,
            social_media_links=social_media_links,
            staff=staff,
        )

    def serialize_short(self):
        return dict(id=str(self.id), name=self.name,)

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
        to=Exhibitor, db_index=True, related_name="links", on_delete=models.CASCADE,
    )
    category = models.CharField(
        max_length=32, default=Category.PROFILE, choices=Category.choices
    )
    display_text = models.CharField(max_length=300, blank=False)
    url = models.URLField(blank=False)


class ExhibitorStaff(models.Model):
    exhibitor = models.ForeignKey(
        to=Exhibitor, db_index=True, related_name="staff", on_delete=models.CASCADE,
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
