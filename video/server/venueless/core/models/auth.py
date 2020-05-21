import uuid

from channels.db import database_sync_to_async
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models

from venueless.core.models.cache import VersionedModel


class User(VersionedModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    client_id = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    token_id = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    world = models.ForeignKey(to="World", db_index=True, on_delete=models.CASCADE)
    profile = JSONField()
    traits = ArrayField(models.CharField(max_length=200), blank=True)

    class Meta:
        unique_together = (("token_id", "world"), ("client_id", "world"))

    def serialize_public(self):
        # Important: If this is updated, venueless.core.services.user.get_public_users also needs to be updated!
        # For performance reasons, it does not use this method directly.
        return {"id": str(self.id), "profile": self.profile}

    def _update_grant_cache(self):
        self._grant_cache = {
            "world": set(self.world_grants.values_list("role", flat=True))
        }
        for v in self.room_grants.values("role", "room"):
            self._grant_cache.setdefault(v["room"], set())
            self._grant_cache[v["room"]].add(v["role"])

    def get_role_grants(self, room=None):
        if self._grant_cache is None:
            self._update_grant_cache()

        roles = self._grant_cache["world"]
        if room:
            roles |= self._grant_cache.get(room.id, set())
        return roles

    async def get_role_grants_async(self, room=None):
        if self._grant_cache is None:
            await database_sync_to_async(self._update_grant_cache)()

        roles = self._grant_cache["world"]
        if room:
            roles |= self._grant_cache.get(room.id, set())
        return roles

    def is_member_of_channel(self, channel_id):
        def update(self):
            self._membership_cache = set(
                str(i) for i in self.chat_channels.values_list("channel_id", flat=True)
            )

        if self._membership_cache is None:
            update(self)
        return str(channel_id) in self._membership_cache

    def clear_caches(self):
        self._membership_cache = None
        self._grant_cache = None


class RoomGrant(models.Model):
    world = models.ForeignKey(
        "World", related_name="room_grants", on_delete=models.CASCADE
    )
    room = models.ForeignKey(
        "Room", related_name="role_grants", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        "User", related_name="room_grants", on_delete=models.CASCADE
    )
    role = models.CharField(max_length=200)

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        self.user.touch()
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        self.user.touch()
        return r


class WorldGrant(models.Model):
    world = models.ForeignKey(
        "World", related_name="world_grants", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        "User", related_name="world_grants", on_delete=models.CASCADE
    )
    role = models.CharField(max_length=200)

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        self.user.touch()
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        self.user.touch()
        return r
