import uuid

from django.db import models


class Exhibitor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=300, null=True)
    description = models.CharField(max_length=500, null=True)
    logo = models.URLField(null=True, blank=True)
    text = models.TextField(null=True)
    header_img = models.URLField(null=True, blank=True)
    size = models.IntegerField(default=0)
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
