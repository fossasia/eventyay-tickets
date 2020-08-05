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
    text = models.TextField(null=True)
    size = models.CharField(max_length=3, default=Sizes.S, choices=Sizes.choices)
    sorting_priority = models.IntegerField(default=0)
    room = models.ForeignKey(
        to="Room", related_name="exhibitors", on_delete=models.CASCADE,
    )
    world = models.ForeignKey(
        to="World", related_name="exhibitors", on_delete=models.CASCADE,
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
    exhibitor = models.ForeignKey(
        to=Exhibitor, db_index=True, related_name="links", on_delete=models.CASCADE,
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

    def serialize(self):
        return dict(
            id=str(self.id),
            exhibitor_id=str(self.exhibitor.id),
            user_id=str(self.user.id),
            state=self.state,
        )
