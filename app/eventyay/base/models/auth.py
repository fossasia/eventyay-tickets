import binascii
import json
import os
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.auth.tokens import default_token_generator
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q, JSONField
from django.utils.crypto import get_random_string, salted_hmac
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_otp.models import Device
from django_scopes import scopes_disabled
from webauthn.helpers.structs import PublicKeyCredentialDescriptor

from eventyay.base.i18n import language
from eventyay.base.models.cache import VersionedModel
from eventyay.helpers.urls import build_absolute_uri

from ...helpers.u2f import pub_key_from_der, websafe_decode
from .base import LoggingMixin


class UserManager(BaseUserManager):
    """
    This is the user manager for our custom user model. See the User
    model documentation to see what's so special about our user model.
    """

    def create_user(self, email: str, password: str = None, **kwargs):
        user = self.model(email=email, **kwargs)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email: str, password: str = None):  # NOQA
        # Not used in the software but required by Django
        if password is None:
            raise Exception('You must provide a password')
        user = self.model(email=email)
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        return user


def generate_notifications_token():
    return get_random_string(length=32)


def generate_session_token():
    return get_random_string(length=32)


def generate_short_token():
    return get_random_string(length=24)

class SuperuserPermissionSet:
    def __contains__(self, item):
        return True



class User(AbstractBaseUser, PermissionsMixin, LoggingMixin, VersionedModel):
    """
    This is the unified user model used by eventyay for both authentication and video/event functionality.


    :param email: The user's email address, used for identification.
    :type email: str
    :param fullname: The user's full name. May be empty or null.
    :type fullname: str
    :param is_active: Whether this user account is activated.
    :type is_active: bool
    :param is_staff: ``True`` for system operators.
    :type is_staff: bool
    :param date_joined: The datetime of the user's registration.
    :type date_joined: datetime
    :param locale: The user's preferred locale code.
    :type locale: str
    :param timezone: The user's preferred timezone.
    :type timezone: str
    """

    class ModerationState(models.TextChoices):
        NONE = ""
        SILENCED = "silenced"
        BANNED = "banned"

    class UserType(models.TextChoices):
        PERSON = "person"
        KIOSK = "kiosk"
        ANONYMOUS = "anon"

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    # Original ticketing fields
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    email = models.EmailField(
        unique=True, db_index=True, null=True, blank=True, verbose_name=_('E-mail'), max_length=190
    )
    fullname = models.CharField(max_length=255, blank=True, null=True, verbose_name=_('Full name'))
    wikimedia_username = models.CharField(max_length=255, blank=True, null=True, verbose_name=('Wikimedia username'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is active'))
    is_staff = models.BooleanField(default=False, verbose_name=_('Is site admin'))
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name=_('Date joined'))
    locale = models.CharField(
        max_length=50, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE, verbose_name=_('Language')
    )
    timezone = models.CharField(max_length=100, default=settings.TIME_ZONE, verbose_name=_('Timezone'))
    require_2fa = models.BooleanField(default=False, verbose_name=_('Two-factor authentication is required to log in'))
    notifications_send = models.BooleanField(
        default=True,
        verbose_name=_('Receive notifications according to my settings below'),
        help_text=_('If turned off, you will not get any notifications.'),
    )
    notifications_token = models.CharField(max_length=255, default=generate_notifications_token)
    auth_backend = models.CharField(max_length=255, default='native')
    session_token = models.CharField(max_length=32, default=generate_session_token)


    # Video/Event fields
    client_id = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    token_id = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    event = models.ForeignKey(to="Event", db_index=True, on_delete=models.CASCADE, null=True, blank=True)
    moderation_state = models.CharField(
        max_length=8,
        default=ModerationState.NONE,
        choices=ModerationState.choices,
    )
    type = models.CharField(
        max_length=8, default=UserType.PERSON, choices=UserType.choices
    )
    show_publicly = models.BooleanField(default=True)
    profile = JSONField(default=dict)
    client_state = JSONField(default=dict)
    traits = JSONField(blank=True, default=list)
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

    # Cache attributes for video functionality
    _grant_cache = None
    _membership_cache = None
    _block_cache = {}
    if TYPE_CHECKING:
        from django.db.models import QuerySet

        from eventyay.base.models import NotificationSetting

        notification_settings: QuerySet[NotificationSetting]

    objects: UserManager = UserManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._teamcache = {}

        self._grant_cache = None
        self._membership_cache = None
        self._block_cache = {}


    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ('email',)

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        is_new = not self.pk
        super().save(*args, **kwargs)
        if is_new:
            self.notification_settings.create(
                action_type='eventyay.event.order.refund.requested',
                event=None,
                method='mail',
                enabled=True,
            )

    def __str__(self):
        return self.email

    # @property
    # def is_superuser(self):
    #    return False

    def get_short_name(self) -> str:
        """
        Returns the first of the following user properties that is found to exist:

        * Full name
        * Email address

        Only present for backwards compatibility
        """
        if self.fullname:
            return self.fullname
        else:
            return self.email

    def get_full_name(self) -> str:
        """
        Returns the first of the following user properties that is found to exist:

        * Full name
        * Wikimedia username
        * Email address
        """
        if self.fullname:
            return self.fullname
        elif self.wikimedia_username:
            return self.wikimedia_username
        else:
            return self.email

    def send_security_notice(self, messages, email=None):
        from eventyay.base.services.mail import SendMailException, mail


        try:
            with language(self.locale):
                msg = '- ' + '\n- '.join(str(m) for m in messages)

            mail(
                email or self.email,
                _('Account information changed'),
                'eventyaycontrol/email/security_notice.txt',
                {'user': self, 'messages': msg, 'url': build_absolute_uri('eventyay_common:account.general')},
                event=None,
                user=self,
                locale=self.locale,
            )
        except SendMailException:
            pass  # Already logged

    def send_password_reset(self):
        from eventyay.base.services.mail import mail

        mail(
            self.email,
            _('Password recovery'),
            'eventyaycontrol/email/forgot.txt',
            {
                'user': self,
                'url': (
                    build_absolute_uri('control:auth.forgot.recover')
                    + '?id=%s&token=%s' % (self.id, default_token_generator.make_token(self))
                ),
            },
            None,
            locale=self.locale,
            user=self,
        )

    @property
    def top_logentries(self):
        return self.all_logentries

    @property
    def all_logentries(self):
        from eventyay.base.models import LogEntry

        return LogEntry.objects.filter(content_type=ContentType.objects.get_for_model(User), object_id=self.pk)

    def _get_teams_for_organizer(self, organizer):
        if 'o{}'.format(organizer.pk) not in self._teamcache:
            self._teamcache['o{}'.format(organizer.pk)] = list(self.teams.filter(organizer=organizer))
        return self._teamcache['o{}'.format(organizer.pk)]

    def _get_teams_for_event(self, organizer, event):
        if 'e{}'.format(event.pk) not in self._teamcache:
            self._teamcache['e{}'.format(event.pk)] = list(
                self.teams.filter(organizer=organizer).filter(Q(all_events=True) | Q(limit_events=event))
            )
        return self._teamcache['e{}'.format(event.pk)]

    def get_event_permission_set(self, organizer, event) -> set:
        """
        Gets a set of permissions (as strings) that a user holds for a particular event

        :param organizer: The organizer of the event
        :param event: The event to check
        :return: set
        """
        teams = self._get_teams_for_event(organizer, event)
        sets = [t.permission_set() for t in teams]
        if sets:
            return set.union(*sets)
        else:
            return set()

    def get_organizer_permission_set(self, organizer) -> set:
        """
        Gets a set of permissions (as strings) that a user holds for a particular organizer

        :param organizer: The organizer of the event
        :return: set
        """
        teams = self._get_teams_for_organizer(organizer)
        sets = [t.permission_set() for t in teams]
        if sets:
            return set.union(*sets)
        else:
            return set()

    def has_event_permission(self, organizer, event, perm_name=None, request=None) -> bool:
        """
        Checks if this user is part of any team that grants access of type ``perm_name``
        to the event ``event``.

        :param organizer: The organizer of the event
        :param event: The event to check
        :param perm_name: The permission, e.g. ``can_change_teams``
        :param request: The current request (optional). Required to detect staff sessions properly.
        :return: bool
        """
        if request and self.has_active_staff_session(request.session.session_key):
            return True
        teams = self._get_teams_for_event(organizer, event)
        if teams:
            self._teamcache['e{}'.format(event.pk)] = teams
            if isinstance(perm_name, (tuple, list)):
                return any([any(team.has_permission(p) for team in teams) for p in perm_name])
            if not perm_name or any([team.has_permission(perm_name) for team in teams]):
                return True
        return False

    def has_organizer_permission(self, organizer, perm_name=None, request=None):
        """
        Checks if this user is part of any team that grants access of type ``perm_name``
        to the organizer ``organizer``.

        :param organizer: The organizer to check
        :param perm_name: The permission, e.g. ``can_change_teams``
        :param request: The current request (optional). Required to detect staff sessions properly.
        :return: bool
        """
        if request and self.has_active_staff_session(request.session.session_key):
            return True
        teams = self._get_teams_for_organizer(organizer)
        if teams:
            if isinstance(perm_name, (tuple, list)):
                return any([any(team.has_permission(p) for team in teams) for p in perm_name])
            if not perm_name or any([team.has_permission(perm_name) for team in teams]):
                return True
        return False

    @scopes_disabled()
    def get_events_with_any_permission(self, request=None):
        """
        Returns a queryset of events the user has any permissions to.

        :param request: The current request (optional). Required to detect staff sessions properly.
        :return: Iterable of Events
        """
        from .event import Event

        if request and self.has_active_staff_session(request.session.session_key):
            return Event.objects.all()

        return Event.objects.filter(
            Q(organizer_id__in=self.teams.filter(all_events=True).values_list('organizer', flat=True))
            | Q(id__in=self.teams.values_list('limit_events__id', flat=True))
        )

    @scopes_disabled()
    def get_events_with_permission(self, permission, request=None):
        """
        Returns a queryset of events the user has a specific permissions to.

        :param request: The current request (optional). Required to detect staff sessions properly.
        :return: Iterable of Events
        """
        from .event import Event

        if request and self.has_active_staff_session(request.session.session_key):
            return Event.objects.all()

        kwargs = {permission: True}

        return Event.objects.filter(
            Q(organizer_id__in=self.teams.filter(all_events=True, **kwargs).values_list('organizer', flat=True))
            | Q(id__in=self.teams.filter(**kwargs).values_list('limit_events__id', flat=True))
        )

    @scopes_disabled()
    def get_organizers_with_permission(self, permission, request=None):
        """
        Returns a queryset of organizers the user has a specific permissions to.

        :param request: The current request (optional). Required to detect staff sessions properly.
        :return: Iterable of Organizers
        """
        from .event import Organizer

        if request and self.has_active_staff_session(request.session.session_key):
            return Organizer.objects.all()

        kwargs = {permission: True}

        return Organizer.objects.filter(id__in=self.teams.filter(**kwargs).values_list('organizer', flat=True))


    def has_active_staff_session(self, session_key=None):
        """
        Returns whether or not a user has an active staff session (formerly known as superuser session)
        with the given session key.
        """
        return self.get_active_staff_session(session_key) is not None

    def get_active_staff_session(self, session_key=None):
        if not self.is_staff:
            return None
        if not hasattr(self, '_staff_session_cache'):
            self._staff_session_cache = {}
        if session_key not in self._staff_session_cache:
            qs = StaffSession.objects.filter(user=self, date_end__isnull=True)
            if session_key:
                qs = qs.filter(session_key=session_key)
            sess = qs.first()
            if sess:
                if sess.date_start < now() - timedelta(seconds=settings.PRETIX_SESSION_TIMEOUT_ABSOLUTE):
                    sess.date_end = now()
                    sess.save()
                    sess = None

            self._staff_session_cache[session_key] = sess
        return self._staff_session_cache[session_key]

    def get_session_auth_hash(self):
        """
        Return an HMAC that needs to
        """
        key_salt = 'eventyay.base.models.User.get_session_auth_hash'
        payload = self.password
        payload += self.email
        payload += self.session_token
        return salted_hmac(key_salt, payload).hexdigest()

    def update_session_token(self):
        self.session_token = generate_session_token()
        self.save(update_fields=['session_token'])

    # Video/Event methods
    def soft_delete(self):
        """Soft delete for video/event functionality"""
        from eventyay.base.models.storage_model import StoredFile

        self.bbb_invites.clear()
        self.room_grants.all().delete()
        self.event_grants.all().delete()
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
        """Serialize user for public display in video/event context"""
        # Important: If this is updated, eventyay.base.services.user.get_public_users also needs to be updated!
        # For performance reasons, it does not use this method directly.
        d = {
            "id": str(self.id),
            "profile": self.profile,
            "pretalx_id": self.pretalx_id,
            "deleted": self.deleted,
            "badges": (
                sorted(
                    list(
                        {
                            badge
                            for trait, badge in trait_badges_map.items()
                            if trait in self.traits
                        }
                    )
                )
                if trait_badges_map
                else []
            ),
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

    # Role and grant methods (video/event)
    def _update_grant_cache(self):
        self._grant_cache = {
            "event": set(self.event_grants.values_list("role", flat=True))
        }
        for v in self.room_grants.values("role", "room"):
            self._grant_cache.setdefault(v["room"], set())
            self._grant_cache[v["room"]].add(v["role"])

    def get_role_grants(self, room=None):
        if self._grant_cache is None:
            self._update_grant_cache()

        roles = self._grant_cache["event"]
        if room:
            roles |= self._grant_cache.get(room.id, set())
        return roles

    async def get_role_grants_async(self, room=None):
        if self._grant_cache is None:
            await database_sync_to_async(self._update_grant_cache)()

        roles = self._grant_cache["event"]
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


# Related models for video/event functionality
class RoomGrant(models.Model):
    event = models.ForeignKey(
        "Event", related_name="room_grants", on_delete=models.CASCADE
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


class EventGrant(models.Model):
    event = models.ForeignKey(
        "Event", related_name="event_grants", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        "User", related_name="event_grants", on_delete=models.CASCADE
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


class ShortToken(models.Model):
    event = models.ForeignKey(
        "Event", related_name="short_tokens", on_delete=models.CASCADE
    )
    expires = models.DateTimeField()
    short_token = models.CharField(
        db_index=True,
        unique=True,
        default=generate_short_token,
        max_length=150,
    )
    long_token = models.TextField()


# Staff session models (from ticketing)
class StaffSession(models.Model):
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    date_start = models.DateTimeField(auto_now_add=True)
    date_end = models.DateTimeField(null=True, blank=True)
    session_key = models.CharField(max_length=255)
    comment = models.TextField()

    class Meta:
        ordering = ('date_start',)


class StaffSessionAuditLog(models.Model):
    session = models.ForeignKey('StaffSession', related_name='logs', on_delete=models.PROTECT)
    datetime = models.DateTimeField(auto_now_add=True)
    url = models.CharField(max_length=255)
    method = models.CharField(max_length=255)
    impersonating = models.ForeignKey('User', null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ('datetime',)


class U2FDevice(Device):
    json_data = models.TextField()

    @property
    def webauthndevice(self):
        d = json.loads(self.json_data)
        return PublicKeyCredentialDescriptor(websafe_decode(d['keyHandle']))

    @property
    def webauthnpubkey(self):
        d = json.loads(self.json_data)
        # We manually need to convert the pubkey from DER format (used in our
        # former U2F implementation) to the format required by webauthn. This
        # is based on the following example:
        # https://www.w3.org/TR/webauthn/#sctn-encoded-credPubKey-examples
        pub_key = pub_key_from_der(websafe_decode(d['publicKey'].replace('+', '-').replace('/', '_')))
        pub_key = binascii.unhexlify(
            'A5010203262001215820{:064x}225820{:064x}'.format(pub_key.public_numbers().x, pub_key.public_numbers().y)
        )
        return pub_key


class WebAuthnDevice(Device):
    credential_id = models.CharField(max_length=255, null=True, blank=True)
    rp_id = models.CharField(max_length=255, null=True, blank=True)
    icon_url = models.CharField(max_length=255, null=True, blank=True)
    ukey = models.TextField(null=True)
    pub_key = models.TextField(null=True)
    sign_count = models.IntegerField(default=0)

    @property
    def webauthndevice(self):
        return PublicKeyCredentialDescriptor(websafe_decode(self.credential_id))

    @property
    def webauthnpubkey(self):
        return websafe_decode(self.pub_key)
