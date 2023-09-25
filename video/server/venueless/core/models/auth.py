import os
import uuid
from datetime import timedelta

from channels.db import database_sync_to_async
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import JSONField
from django.utils.crypto import get_random_string
from django.utils.timezone import now

from venueless.core.models.cache import VersionedModel


class User(VersionedModel):
    class ModerationState(models.TextChoices):
        NONE = ""
        SILENCED = "silenced"
        BANNED = "banned"

    class UserType(models.TextChoices):
        PERSON = "person"
        KIOSK = "kiosk"
        ANONYMOUS = "anon"

    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    client_id = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    token_id = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    world = models.ForeignKey(to="World", db_index=True, on_delete=models.CASCADE)
    moderation_state = models.CharField(
        max_length=8, default=ModerationState.NONE, choices=ModerationState.choices
    )
    type = models.CharField(
        max_length=8, default=UserType.PERSON, choices=UserType.choices
    )
    show_publicly = models.BooleanField(default=True)
    profile = JSONField()
    client_state = JSONField(default=dict)
    traits = ArrayField(models.CharField(max_length=200), blank=True)
    pretalx_id = models.CharField(max_length=200, null=True, blank=True)
    blocked_users = models.ManyToManyField(
        "self", related_name="blocked_by", symmetrical=False
    )
    last_login = models.DateTimeField(null=True, blank=True)
    deleted = models.BooleanField(default=False)
    social_login_id_twitter = models.CharField(
        null=True, blank=True, max_length=190, db_index=True
    )
    social_login_id_linkedin = models.CharField(
        null=True, blank=True, max_length=190, db_index=True
    )

    class Meta:
        unique_together = (("token_id", "world"), ("client_id", "world"))

    def soft_delete(self):
        from venueless.storage.models import StoredFile

        self.bbb_invites.clear()
        self.room_grants.all().delete()
        self.world_grants.all().delete()
        self.rouletterequest_set.all().delete()
        self.roulette_pairing_left.all().delete()
        self.roulette_pairing_right.all().delete()
        self.audit_logs.filter(
            type__startswith="auth.user.profile",
            data__object=str(self.pk),
        ).update(
            data={
                "object": str(self.pk),
                "old": {"__redacted": True},
                "new": {"__redacted": True},
            }
        )
        self.exhibitor_staff.all().delete()
        self.poster_presenter.all().delete()
        self.chat_channels.filter(channel__room__isnull=False).delete()

        for dm_channel in self.chat_channels.filter(channel__room__isnull=True):
            if dm_channel.channel.members.filter(user__deleted=False).count() == 1:
                # Last one standing, delete DM channel including all messages as well as shared pictures
                for event in dm_channel.channel.chat_events.filter(
                    event_type="channel.message"
                ):
                    if event.content.get("files", []):
                        for file in event.content.get("files", []):
                            basename = os.path.basename(file["url"])
                            fileid = basename.split(".")[0]
                            sf = StoredFile.objects.filter(id=fileid, user=self).first()
                            if sf:
                                sf.full_delete()
                dm_channel.channel.delete()

        if "avatar" in self.profile and "url" in self.profile["avatar"]:
            basename = os.path.basename(self.profile["avatar"]["url"])
            fileid = basename.split(".")[0]
            sf = StoredFile.objects.filter(id=fileid, user=self).first()
            if sf:
                sf.full_delete()

        self.deleted = True
        self.client_id = None
        self.token_id = None
        self.show_publicly = False
        self.profile = {}
        self.save()

    def serialize_public(
        self,
        include_admin_info=False,
        trait_badges_map=None,
        include_client_state=False,
    ):
        # Important: If this is updated, venueless.core.services.user.get_public_users also needs to be updated!
        # For performance reasons, it does not use this method directly.
        d = {
            "id": str(self.id),
            "profile": self.profile,
            "pretalx_id": self.pretalx_id,
            "deleted": self.deleted,
            "badges": sorted(
                list(
                    {
                        badge
                        for trait, badge in trait_badges_map.items()
                        if trait in self.traits
                    }
                )
            )
            if trait_badges_map
            else [],
        }
        d["inactive"] = self.last_login is None or self.last_login < now() - timedelta(
            hours=36
        )
        if include_admin_info:
            d["moderation_state"] = self.moderation_state
            d["token_id"] = self.token_id
        if include_client_state:
            d["client_state"] = self.client_state
        return d

    @property
    def is_banned(self):
        return self.moderation_state == self.ModerationState.BANNED or self.deleted

    @property
    def is_silenced(self):
        return self.moderation_state == self.ModerationState.SILENCED

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

    def _update_membership_cache(self):
        self._membership_cache = {
            str(i) for i in self.chat_channels.values_list("channel_id", flat=True)
        }

    async def is_member_of_channel_async(self, channel_id):
        if self._membership_cache is None:
            await database_sync_to_async(self._update_membership_cache)()
        return str(channel_id) in self._membership_cache

    async def is_blocked_in_channel_async(self, channel):
        if channel.room:
            return False
        if channel.id not in self._block_cache:

            @database_sync_to_async
            def _add():
                self._block_cache[channel.id] = channel.members.filter(
                    user__in=self.blocked_by.all()
                ).exists()

            await _add()
        return self._block_cache[channel.id]

    def clear_caches(self):
        self._membership_cache = None
        self._grant_cache = None
        self._block_cache = {}


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


def generate_short_token():
    return get_random_string(length=24)


class ShortToken(models.Model):
    world = models.ForeignKey(
        "World", related_name="short_tokens", on_delete=models.CASCADE
    )
    expires = models.DateTimeField()
    short_token = models.CharField(
        db_index=True, unique=True, default=generate_short_token, max_length=150
    )
    long_token = models.TextField()
