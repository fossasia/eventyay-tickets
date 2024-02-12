import json
import random
import uuid
from contextlib import suppress
from hashlib import md5
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from django_scopes import scopes_disabled
from rest_framework.authtoken.models import Token

from pretalx.common.mixins.models import FileCleanupMixin, GenerateCode
from pretalx.common.models import TIMEZONE_CHOICES
from pretalx.common.urls import build_absolute_uri
from pretalx.common.utils import path_with_hash


def avatar_path(instance, filename):
    return f"avatars/{path_with_hash(filename)}"


class UserManager(BaseUserManager):
    """The user manager class."""

    def create_user(self, password: str = None, **kwargs):
        user = self.model(**kwargs)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, password: str, **kwargs):
        user = self.create_user(password=password, **kwargs)
        user.is_staff = True
        user.is_administrator = True
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_administrator", "is_superuser"])
        return user


class User(PermissionsMixin, GenerateCode, FileCleanupMixin, AbstractBaseUser):
    """The pretalx user model.

    Users describe all kinds of persons who interact with pretalx: Organisers, reviewers, submitters, speakers.

    :param code: A user's alphanumeric code is auto generated, may not be
        changed, and is the unique identifier of that user.
    :param name: A name fit for public display. Will be used in the user
        interface and for public display for all speakers in all of their
        events.
    :param password: The password is stored using Django's PasswordField. Use
        the ``set_password`` and ``check_password`` methods to interact with it.
    :param nick: The nickname field has been deprecated and is scheduled to be
        deleted. Use the email field instead.
    :param groups: Django internals, not used in pretalx.
    :param user_permissions: Django internals, not used in pretalx.
    """

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"

    objects = UserManager()

    code = models.CharField(max_length=16, unique=True, null=True)
    nick = models.CharField(max_length=60, null=True, blank=True)
    name = models.CharField(
        max_length=120,
        verbose_name=_("Name"),
        help_text=_(
            "Please enter the name you wish to be displayed publicly. This name will be used for all events you are participating in on this server."
        ),
    )
    email = models.EmailField(
        unique=True,
        verbose_name=_("E-mail"),
        help_text=_(
            "Your email address will be used for password resets and notification about your event/proposals."
        ),
    )
    is_active = models.BooleanField(
        default=True, help_text="Inactive users are not allowed to log in."
    )
    is_staff = models.BooleanField(
        default=False, help_text="A default Django flag. Not in use in pretalx."
    )
    is_administrator = models.BooleanField(
        default=False,
        help_text="Should only be ``True`` for people with administrative access to the server pretalx runs on.",
    )
    is_superuser = models.BooleanField(
        default=False,
        help_text="Never set this flag to ``True``, since it short-circuits all authorisation mechanisms.",
    )
    locale = models.CharField(
        max_length=32,
        default=settings.LANGUAGE_CODE,
        choices=settings.LANGUAGES,
        verbose_name=_("Preferred language"),
    )
    timezone = models.CharField(
        choices=[(tz, tz) for tz in TIMEZONE_CHOICES],
        max_length=32,
        default="UTC",
    )
    avatar = models.ImageField(
        null=True,
        blank=True,
        verbose_name=_("Profile picture"),
        help_text=_("If possible, upload an image that is least 120 pixels wide."),
        upload_to=avatar_path,
    )
    get_gravatar = models.BooleanField(
        default=False,
        verbose_name=_("Retrieve profile picture via gravatar"),
        help_text=_(
            "If you have registered with an email address that has a gravatar account, we can retrieve your profile picture from there."
        ),
    )
    pw_reset_token = models.CharField(
        null=True, max_length=160, verbose_name="Password reset token"
    )
    pw_reset_time = models.DateTimeField(null=True, verbose_name="Password reset time")

    def __str__(self) -> str:
        """For public consumption as it is used for Select widgets, e.g. on the
        feedback form."""
        return self.name or str(_("Unnamed user"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.permission_cache = {}
        self.team_permissions = {}

    def has_perm(self, perm, obj, *args, **kwargs):
        cached_result = None
        with suppress(TypeError):
            cached_result = self.permission_cache.get((perm, obj))
        if cached_result is not None:
            return cached_result
        result = super().has_perm(perm, obj, *args, **kwargs)
        self.permission_cache[(perm, obj)] = result
        return result

    def get_display_name(self) -> str:
        """Returns a user's name or 'Unnamed user'."""
        return self.name if self.name else str(_("Unnamed user"))

    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        result = super().save(*args, **kwargs)

        # Check if we need to get the profile picture from gravatar
        update_gravatar = (
            not kwargs.get("update_fields") or "get_gravatar" in kwargs["update_fields"]
        )
        if self.get_gravatar and update_gravatar:
            from pretalx.person.tasks import gravatar_cache

            gravatar_cache.apply_async(args=(self.pk,))
        return result

    def event_profile(self, event):
        """Retrieve (and/or create) the event.

        :class:`~pretalx.person.models.profile.SpeakerProfile` for this user.

        :type event: :class:`pretalx.event.models.event.Event`
        :retval: :class:`pretalx.person.models.profile.EventProfile`
        """
        from pretalx.person.models.profile import SpeakerProfile

        try:
            return self.profiles.select_related("event").get(event=event)
        except Exception:
            profile = SpeakerProfile(event=event, user=self)
            if self.pk:
                profile.save()
            return profile

    def get_locale_for_event(self, event):
        if self.locale in event.locales:
            return self.locale
        return event.locale

    def log_action(
        self, action: str, data: dict = None, person=None, orga: bool = False
    ):
        """Create a log entry for this user.

        :param action: The log action that took place.
        :param data: Addition data to be saved.
        :param person: The person modifying this user. Defaults to this user.
        :type person: :class:`~pretalx.person.models.user.User`
        :param orga: Was this action initiated by a privileged user?
        """
        from pretalx.common.models import ActivityLog

        if data:
            data = json.dumps(data)

        ActivityLog.objects.create(
            person=person or self,
            content_object=self,
            action_type=action,
            data=data,
            is_orga_action=orga,
        )

    def logged_actions(self):
        """Returns all log entries that were made about this user."""
        from pretalx.common.models import ActivityLog

        return ActivityLog.objects.filter(
            content_type=ContentType.objects.get_for_model(type(self)),
            object_id=self.pk,
        )

    def own_actions(self):
        """Returns all log entries that were made by this user."""
        from pretalx.common.models import ActivityLog

        return ActivityLog.objects.filter(person=self)

    @transaction.atomic
    def deactivate(self):
        """Delete the user by unsetting all of their information."""
        from pretalx.submission.models import Answer

        self.email = f"deleted_user_{random.randint(0, 999)}@localhost"
        while self.__class__.objects.filter(
            email__iexact=self.email
        ).exists():  # pragma: no cover
            self.email = f"deleted_user_{random.randint(0, 999)}"
        self.name = "Deleted User"
        self.is_active = False
        self.is_superuser = False
        self.is_administrator = False
        self.locale = "en"
        self.timezone = "UTC"
        self.pw_reset_token = None
        self.pw_reset_time = None
        self.set_unusable_password()
        self.save()
        self.profiles.all().update(biography="")
        for answer in Answer.objects.filter(
            person=self, question__contains_personal_data=True
        ):
            answer.delete()  # Iterate to delete answer files, too
        self._delete_files()
        for team in self.teams.all():
            team.members.remove(self)

    deactivate.alters_data = True

    @transaction.atomic
    def shred(self):
        """Actually remove the user account."""
        from pretalx.submission.models import Submission

        with scopes_disabled():
            if (
                Submission.all_objects.filter(speakers__in=[self]).count()
                or self.teams.count()
                or self.answers.count()
            ):
                raise Exception(
                    f"Cannot delete user <{self.email}> because they have submissions, answers, or teams. Please deactivate this user instead."
                )
            self.logged_actions().delete()
            self.own_actions().update(person=None)
            self._delete_files()
            self.delete()

    shred.alters_data = True

    @cached_property
    def guid(self) -> str:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"acct:{self.email.strip()}").__str__()

    @cached_property
    def gravatar_parameter(self) -> str:
        return md5(self.email.strip().encode()).hexdigest()

    @cached_property
    def has_avatar(self) -> bool:
        return self.avatar and self.avatar != "False"

    @cached_property
    def avatar_url(self) -> str:
        if self.has_avatar:
            return self.avatar.url

    def get_avatar_url(self, event=None):
        """Returns the full avatar URL, where user.avatar_url returns the
        absolute URL."""
        if not self.avatar_url:
            return ""
        if event and event.custom_domain:
            return urljoin(event.custom_domain, self.avatar_url)
        return urljoin(settings.SITE_URL, self.avatar_url)

    def get_events_with_any_permission(self):
        """Returns a queryset of events for which this user has any type of
        permission."""
        from pretalx.event.models import Event

        if self.is_administrator:
            return Event.objects.all()

        return Event.objects.filter(
            Q(
                organiser_id__in=self.teams.filter(all_events=True).values_list(
                    "organiser", flat=True
                )
            )
            | Q(id__in=self.teams.values_list("limit_events__id", flat=True))
        )

    def get_events_for_permission(self, **kwargs):
        """Returns a queryset of events for which this user as all of the given
        permissions.

        Permissions are given as named arguments, e.g.
        ``get_events_for_permission(is_reviewer=True)``.
        """
        from pretalx.event.models import Event

        if self.is_administrator:
            return Event.objects.all()

        orga_teams = self.teams.filter(**kwargs)
        absolute = orga_teams.filter(all_events=True).values_list(
            "organiser", flat=True
        )
        relative = orga_teams.filter(all_events=False).values_list(
            "limit_events", flat=True
        )
        return Event.objects.filter(
            models.Q(organiser__in=absolute) | models.Q(pk__in=relative)
        ).distinct()

    def get_permissions_for_event(self, event) -> set:
        """Returns a set of all permission a user has for the given event.

        :type event: :class:`~pretalx.event.models.event.Event`
        """
        if self.is_administrator:
            return {
                "can_create_events",
                "can_change_teams",
                "can_change_organiser_settings",
                "can_change_event_settings",
                "can_change_submissions",
                "is_reviewer",
            }
        teams = event.teams.filter(members__in=[self])
        if not teams:
            return set()
        return set().union(*[team.permission_set for team in teams])

    def regenerate_token(self) -> Token:
        """Generates a new API access token, deleting the old one."""
        self.log_action(action="pretalx.user.token.reset")
        Token.objects.filter(user=self).delete()
        return Token.objects.create(user=self)

    regenerate_token.alters_data = True

    def get_password_reset_url(self, event=None, orga=False):
        if event:
            path = "orga:event.auth.recover" if orga else "cfp:event.recover"
            url = build_absolute_uri(
                path,
                kwargs={"token": self.pw_reset_token, "event": event.slug},
            )
        else:
            url = build_absolute_uri(
                "orga:auth.recover", kwargs={"token": self.pw_reset_token}
            )
        return url

    @transaction.atomic
    def reset_password(self, event, user=None, mail_text=None, orga=False):
        from pretalx.mail.models import QueuedMail

        self.pw_reset_token = get_random_string(32)
        self.pw_reset_time = now()
        self.save()

        context = {
            "name": self.name or "",
            "url": self.get_password_reset_url(event=event, orga=orga),
        }
        if not mail_text:
            mail_text = _(
                """Hi {name},

you have requested a new password for your pretalx account.
To reset your password, click on the following link:

  {url}

If this wasn\'t you, you can just ignore this email.

All the best,
the pretalx robot"""
            )

        with override(self.locale):
            mail = QueuedMail.objects.create(
                subject=_("Password recovery"),
                text=str(mail_text).format(**context),
                locale=self.locale,
            )
            mail.to_users.add(self)
            mail.send()
        self.log_action(
            action="pretalx.user.password.reset", person=user, orga=bool(user)
        )

    reset_password.alters_data = True
