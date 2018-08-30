import json
import random
from hashlib import md5

import pytz
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin,
)
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import get_language, ugettext_lazy as _
from rest_framework.authtoken.models import Token

from pretalx.common.urls import build_absolute_uri


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
        user.save(update_fields=['is_staff', 'is_administrator', 'is_superuser'])
        return user


def assign_code(obj, length=6):
    # This omits some character pairs completely because they are hard to read even on screens (1/I and O/0)
    # and includes only one of two characters for some pairs because they are sometimes hard to distinguish in
    # handwriting (2/Z, 4/A, 5/S, 6/G).
    while True:
        code = get_random_string(length=length, allowed_chars=User.CODE_CHARSET)

        if not User.objects.filter(code__iexact=code).exists():
            obj.code = code
            return code


class User(PermissionsMixin, AbstractBaseUser):
    """
    The pretalx user model.

    We don't really need last names and fancy stuff, so we stick with a name and an email address.
    """

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    CODE_CHARSET = list('ABCDEFGHJKLMNPQRSTUVWXYZ3789')

    objects = UserManager()

    code = models.CharField(max_length=16, unique=True, null=True)
    nick = models.CharField(max_length=60, null=True, blank=True)
    name = models.CharField(
        max_length=120,
        verbose_name=_('Name'),
        help_text=_('Please enter the name you wish to be displayed publicly.'),
    )
    email = models.EmailField(
        unique=True,
        verbose_name=_('E-Mail'),
        help_text=_(
            'Your email address will be used for password resets and notification about your event/submissions.'
        ),
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_administrator = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    locale = models.CharField(
        max_length=32,
        default=settings.LANGUAGE_CODE,
        choices=settings.LANGUAGES,
        verbose_name=_('Preferred language'),
    )
    timezone = models.CharField(
        choices=[(tz, tz) for tz in pytz.common_timezones], max_length=30, default='UTC'
    )
    avatar = models.ImageField(
        null=True,
        blank=True,
        verbose_name=_('Profile picture'),
        help_text=_('Optional. Will be displayed publicly.'),
    )
    get_gravatar = models.BooleanField(
        default=False,
        verbose_name=_('Retrieve profile picture via gravatar'),
        help_text=_(
            'If you have registered with an email address that has a gravatar account, we can retrieve your profile picture from there.'
        ),
    )
    pw_reset_token = models.CharField(null=True, max_length=160)
    pw_reset_time = models.DateTimeField(null=True)

    def __str__(self) -> str:
        """Use a useful string representation."""
        return self.get_display_name()

    def get_display_name(self) -> str:
        return self.name if self.name else str(_('Unnamed user'))

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        if not self.code:
            assign_code(self)
        return super().save(args, kwargs)

    def event_profile(self, event):
        return self.profiles.get_or_create(event=event)[0]

    def log_action(self, action, data=None, person=None, orga=False):
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
        from pretalx.common.models import ActivityLog

        return ActivityLog.objects.filter(
            content_type=ContentType.objects.get_for_model(type(self)),
            object_id=self.pk,
        )

    def own_actions(self):
        from pretalx.common.models import ActivityLog

        return ActivityLog.objects.filter(person=self)

    def deactivate(self):
        from pretalx.submission.models import Answer

        self.email = f'deleted_user_{random.randint(0, 999)}@localhost'
        while self.__class__.objects.filter(email__iexact=self.email).exists():
            self.email = f'deleted_user_{random.randint(0, 999)}'
        self.name = 'Deleted User'
        self.is_active = False
        self.is_superuser = False
        self.is_administrator = False
        self.locale = 'en'
        self.timezone = 'UTC'
        self.pw_reset_token = None
        self.pw_reset_time = None
        self.save()
        self.profiles.all().update(biography='')
        Answer.objects.filter(
            person=self, question__contains_personal_data=True
        ).delete()
        for team in self.teams.all():
            team.members.remove(self)

    @cached_property
    def gravatar_parameter(self):
        return md5(self.email.strip().encode()).hexdigest()

    def get_events_for_permission(self, **kwargs):
        from pretalx.event.models import Event

        orga_teams = self.teams.filter(**kwargs)
        absolute = orga_teams.filter(all_events=True).values_list(
            'organiser', flat=True
        )
        relative = orga_teams.filter(all_events=False)
        return Event.objects.filter(
            models.Q(organiser__in=absolute) | models.Q(organiser__teams__in=relative)
        ).distinct()

    def get_permissions_for_event(self, event):
        if self.is_administrator:
            return {
                'can_create_events',
                'can_change_teams',
                'can_change_organiser_settings',
                'can_change_event_settings',
                'can_change_submissions',
                'is_reviewer',
            }
        teams = event.teams.filter(members__in=[self])
        if not teams:
            return set()
        return set().union(*[team.permission_set for team in teams])

    def remaining_override_votes(self, event):
        allowed = (
            max(
                event.teams.filter(members__in=[self], is_reviewer=True).values_list(
                    'review_override_votes', flat=True
                )
            )
            or 0
        )
        overridden = self.reviews.filter(
            submission__event=event, override_vote__isnull=False
        ).count()
        return max(allowed - overridden, 0)

    def regenerate_token(self):
        self.log_action(action='pretalx.user.token.reset')
        Token.objects.filter(user=self).delete()
        return Token.objects.create(user=self)

    def reset_password(self, event, user=None):
        from pretalx.common.mail import mail

        with transaction.atomic():
            self.pw_reset_token = get_random_string(32)
            self.pw_reset_time = now()
            self.save()
            mail(
                self,
                _('Password recovery'),
                event.settings.mail_text_reset,
                {
                    'name': self.name or '',
                    'event': event.name,
                    'url': build_absolute_uri(
                        'cfp:event.recover',
                        event=event,
                        kwargs={'event': event.slug, 'token': self.pw_reset_token},
                    ),
                },
                event,
                locale=get_language(),
            )
            self.log_action(
                action='pretalx.user.password.reset', person=user, orga=bool(user)
            )
