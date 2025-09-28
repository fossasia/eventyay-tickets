import binascii
from contextlib import suppress
from hashlib import md5
import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urljoin
import uuid

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.auth.tokens import default_token_generator
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.http import HttpRequest
from django.urls import reverse
from django.utils.crypto import get_random_string, salted_hmac
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_otp.models import Device
from django_scopes import scopes_disabled
from rest_framework.authtoken.models import Token
from rules.contrib.models import RulesModelBase, RulesModelMixin
from webauthn.helpers.structs import PublicKeyCredentialDescriptor

from eventyay.base.i18n import language
from eventyay.common.image import create_thumbnail
from eventyay.common.text.path import path_with_hash
from eventyay.helpers.urls import build_absolute_uri
from eventyay.talk_rules.person import is_administrator

from ...helpers.u2f import pub_key_from_der, websafe_decode
from .base import LoggingMixin
from .mixins import FileCleanupMixin, GenerateCode

logger = logging.getLogger(__name__)


def avatar_path(instance, filename):
    if instance.code:
        extension = Path(filename).suffix
        filename = f'{instance.code}{extension}'
    return path_with_hash(filename, base_path='avatars')


class UserQuerySet(models.QuerySet):
    def with_profiles(self, event):
        from django.db.models import Prefetch

        from eventyay.base.models.profile import SpeakerProfile

        return self.prefetch_related(
            Prefetch(
                'profiles',
                queryset=SpeakerProfile.objects.filter(event=event).select_related('event'),
                to_attr='_event_profiles',
            ),
        ).distinct()


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
        user.is_administrator = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        return user


def generate_notifications_token():
    return get_random_string(length=32)


def generate_session_token():
    return get_random_string(length=32)


class SuperuserPermissionSet:
    def __contains__(self, item):
        return True


class User(
    PermissionsMixin,
    LoggingMixin,
    RulesModelMixin,
    GenerateCode,
    FileCleanupMixin,
    AbstractBaseUser,
    metaclass=RulesModelBase,
):
    """
    This is the user model used by eventyay for authentication.

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

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = []

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

    # From Talk
    code = models.CharField(max_length=16, unique=True, null=True)
    nick = models.CharField(max_length=60, null=True, blank=True)
    is_administrator = models.BooleanField(
        default=False,
        help_text='Should only be ``True`` for people with administrative access to the server eventyay runs on.',
    )
    avatar = models.ImageField(
        null=True,
        blank=True,
        verbose_name=_('Profile picture'),
        help_text=_(
            'We recommend uploading an image at least 400px wide. '
            'A square image works best, as we display it in a circle in several places.'
        ),
        upload_to=avatar_path,
    )
    avatar_thumbnail = models.ImageField(null=True, blank=True, upload_to='avatars/')
    avatar_thumbnail_tiny = models.ImageField(null=True, blank=True, upload_to='avatars/')
    get_gravatar = models.BooleanField(
        default=False,
        verbose_name=_('Retrieve profile picture via gravatar'),
        help_text=_(
            'If you have registered with an email address that has a gravatar account, we can retrieve your profile picture from there.'
        ),
    )
    avatar_source = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Profile Picture Source'),
        help_text=_('Please enter the name of the author or source of image and a link if applicable.'),
    )
    avatar_license = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Profile Picture License'),
        help_text=_('Please enter the name of the license of the photo and link to it if applicable.'),
    )
    pw_reset_token = models.CharField(null=True, max_length=160, verbose_name='Password reset token')
    pw_reset_time = models.DateTimeField(null=True, verbose_name='Password reset time')

    # ====

    if TYPE_CHECKING:
        from django.db.models import QuerySet

        from eventyay.base.models import NotificationSetting

        notification_settings: QuerySet[NotificationSetting]

    objects = UserManager().from_queryset(UserQuerySet)()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._teamcache = {}
        self.permission_cache = {}
        self.event_profile_cache = {}
        self.event_permission_cache = {}

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ('email',)
        rules_permissions = {
            'administrator': is_administrator,
        }

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        is_new = not self.pk
        # Check if we need to get the profile picture from gravatar
        update_gravatar = not kwargs.get('update_fields') or 'get_gravatar' in kwargs['update_fields']
        super().save(*args, **kwargs)
        if self.get_gravatar and update_gravatar:
            from eventyay.person.tasks import gravatar_cache

            gravatar_cache.apply_async(args=(self.pk,), ignore_result=True)
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

    def send_password_reset(self, request: HttpRequest):
        from eventyay.base.services.mail import mail

        subject = _('Password recovery')
        security_token = default_token_generator.make_token(self)
        base_action_url = reverse('eventyay_common:auth.forgot.recover')
        params = {
            'id': self.id,
            'token': security_token,
        }
        action_url = request.build_absolute_uri(f'{base_action_url}?{urlencode(params)}')
        logger.info('Action URL for %s to reset password: %s', self.email, action_url)
        context = {'user': self, 'url': action_url}
        mail(
            self.email,
            subject,
            'eventyay/email/forgot.txt.jinja',
            context,
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

    # From talk
    def get_display_name(self) -> str:
        """Returns a user's name or 'Unnamed user'."""
        return str(self.fullname) if self.fullname else str(self)

    def has_perm(self, perm, obj, *args, **kwargs):
        cached_result = None
        with suppress(TypeError):
            cached_result = self.permission_cache.get((perm, obj))
        if cached_result is not None:
            return cached_result
        result = super().has_perm(perm, obj, *args, **kwargs)
        self.permission_cache[(perm, obj)] = result
        return result

    def event_profile(self, event):
        """Retrieve (and/or create) the event.

        :class:`~eventyay.base.models.profile.SpeakerProfile` for this user.

        :type event: :class:`eventyay.base.models.event.Event`
        :retval: :class:`eventyay.base.models.profile.EventProfile`
        """
        if profile := self.event_profile_cache.get(event.pk):
            return profile

        if hasattr(self, '_event_profiles') and len(self._event_profiles) == 1:
            profile = self._event_profiles[0]
            if profile.event_id == event.pk:
                self.event_profile_cache[event.pk] = profile
                return profile

        try:
            profile = self.profiles.select_related('event').get(event=event)
        except Exception:
            from eventyay.base.models.profile import SpeakerProfile

            profile = SpeakerProfile(event=event, user=self)
            if self.pk:
                profile.save()

        self.event_profile_cache[event.pk] = profile
        return profile

    def get_locale_for_event(self, event):
        if self.locale in event.locales:
            return self.locale
        return event.locale

    @cached_property
    def guid(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f'acct:{self.email.strip()}'))

    @cached_property
    def gravatar_parameter(self) -> str:
        return md5(self.email.strip().encode()).hexdigest()

    @cached_property
    def has_avatar(self) -> bool:
        return bool(self.avatar) and self.avatar != 'False'

    @cached_property
    def avatar_url(self) -> str:
        if self.has_avatar:
            return self.avatar.url

    def get_avatar_url(self, event=None, thumbnail=None):
        """Returns the full avatar URL, where user.avatar_url returns the
        absolute URL."""
        if not self.avatar_url:
            return ''
        if not thumbnail:
            image = self.avatar
        else:
            image = self.avatar_thumbnail_tiny if thumbnail == 'tiny' else self.avatar_thumbnail
            if not image:
                image = create_thumbnail(self.avatar, thumbnail)
        if not image:
            return
        if event and event.custom_domain:
            return urljoin(event.custom_domain, image.url)
        return urljoin(settings.SITE_URL, image.url)

    def regenerate_token(self) -> Token:
        """Generates a new API access token, deleting the old one."""
        self.log_action(action='eventyay.user.token.reset')
        Token.objects.filter(user=self).delete()
        return Token.objects.create(user=self)

    regenerate_token.alters_data = True

    def get_permissions_for_event(self, event) -> set:
        """Returns a set of all permission a user has for the given event.

        :type event: :class:`~eventyay.base.models.event.Event`
        """
        if permissions := self.event_permission_cache.get(event.pk):
            return permissions
        if self.is_administrator:
            return {
                'can_create_events',
                'can_change_teams',
                'can_change_organiser_settings',
                'can_change_event_settings',
                'can_change_submissions',
                'is_reviewer',
            }
        permissions = set()
        teams = event.teams.filter(members__in=[self])
        if teams:
            permissions = set().union(*[team.permission_set() for team in teams])
        self.event_permission_cache[event.pk] = permissions
        return permissions


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
