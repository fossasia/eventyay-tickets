import uuid

from django.db import models


class Exhibitor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=300, null=True)
    description = models.CharField(max_length=500, null=True)
    text = models.TextField(null=True)
    grid_color = models.CharField(max_length=6, null=True)
    # TODO: header & tile img
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


class ExhibitorStaff(models.Model):
    exhibitor = models.ForeignKey(
        to=Exhibitor,
        max_length=300,
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
