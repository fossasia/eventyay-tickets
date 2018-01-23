import json
import random
import re
import string
from hashlib import md5

import pytz
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin,
)
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _


def nick_validator(value: str) -> None:
    """
    Validate nicknames for length, collisions when lower-cased, and allowed
    characters (ascii letters, digits, -, _). To be used in URL.
    """
    if not 2 <= len(value) <= 60:
        raise ValidationError('The nick must be between 2 and 60 characters long.')

    allowed = string.ascii_uppercase + string.ascii_lowercase + string.digits + '\-_'
    if not re.compile(rf'^[{allowed}]+$').search(value):
        raise ValidationError('The nick may only contain ascii letters, digits and -_.')


class UserManager(BaseUserManager):
    """
    The user manager class
    """
    def create_user(self, nick: str, password: str=None, **kwargs):
        user = self.model(nick=nick, **kwargs)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, nick: str, password: str, **kwargs):
        user = self.create_user(nick=nick, password=password, **kwargs)
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
    The pretalx user model: We don't really need last names and fancy stuff, so
    we stick with a nick, and optionally a name and an email address.
    """
    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'nick'
    CODE_CHARSET = list('ABCDEFGHJKLMNPQRSTUVWXYZ3789')

    objects = UserManager()

    code = models.CharField(
        max_length=16,
        unique=True, null=True,
    )
    nick = models.CharField(
        max_length=60, unique=True, validators=[nick_validator],
        verbose_name=_('Nickname'),
        help_text=_('Please use only characters in the latin alphabet, plus numbers and _-.'),
    )
    name = models.CharField(
        max_length=120, null=True, blank=True, verbose_name=_('Name'),
        help_text=_('Please enter the name you wish to be displayed.'),
    )
    email = models.EmailField(
        verbose_name=_('E-Mail'),
        help_text=_('Your email address will be used for password resets and notification about your event/submissions.'),
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_administrator = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    locale = models.CharField(max_length=32, default=settings.LANGUAGE_CODE,
                              choices=settings.LANGUAGES,
                              verbose_name=_('Preferred language'))
    timezone = models.CharField(
        choices=[(tz, tz) for tz in pytz.common_timezones],
        max_length=30,
        default='UTC',
    )
    avatar = models.ImageField(
        null=True, blank=True,
        verbose_name=_('Profile picture'),
        help_text=_('Optional. Will be displayed publically.'),
    )
    get_gravatar = models.BooleanField(
        default=False,
        verbose_name=_('Retrieve profile picture via gravatar'),
        help_text=_('If you have registered with an email address that has a gravatar account, we can retrieve your profile picture from there.'),
    )
    pw_reset_token = models.CharField(null=True, max_length=160)
    pw_reset_time = models.DateTimeField(null=True)

    def __str__(self) -> str:
        return self.get_display_name()

    def get_full_name(self) -> str:
        # TODO: Django 2.0: remove
        return ''

    def get_display_name(self) -> str:
        return self.name if self.name else self.nick

    def get_short_name(self) -> str:
        # TODO: Django 2.0: remove
        return ''

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        if not self.code:
            assign_code(self)
        return super().save(args, kwargs)

    def log_action(self, action, data=None, person=None, orga=False):
        from pretalx.common.models import ActivityLog
        if data:
            data = json.dumps(data)

        ActivityLog.objects.create(
            person=person or self, content_object=self, action_type=action,
            data=data, is_orga_action=orga,
        )

    def logged_actions(self):
        from pretalx.common.models import ActivityLog

        return ActivityLog.objects.filter(
            content_type=ContentType.objects.get_for_model(type(self)),
            object_id=self.pk
        )

    def own_actions(self):
        from pretalx.common.models import ActivityLog
        return ActivityLog.objects.filter(person=self)

    def deactivate(self):
        from pretalx.person.models import EventPermission
        from pretalx.submission.models import Answer
        self.nick = f'deleted_user_{random.randint(0, 999)}'
        while self.__class__.objects.filter(nick__iexact=self.nick).exists():
            self.nick = f'deleted_user_{random.randint(0, 999)}'
        self.name = 'Deleted User'
        self.email = f'{self.nick}@localhost'
        self.is_active = False
        self.is_superuser = False
        self.is_administrator = False
        self.locale = 'en'
        self.timezone = 'UTC'
        self.pw_reset_token = None
        self.pw_reset_time = None
        self.save()
        self.profiles.all().update(biography='')
        EventPermission.objects.filter(user=self).update(is_orga=False, invitation_email=None, invitation_token=None)
        Answer.objects.filter(person=self, question__contains_personal_data=True).delete()

    @property
    def gravatar_parameter(self):
        return md5(self.email.strip().encode()).hexdigest()

    def remaining_override_votes(self, event):
        permission = self.permissions.filter(event=event).first()
        if not permission:
            return 0
        if permission.review_override_count:
            overridden = self.reviews.filter(submission__event=event, override_vote__isnull=False).count()
            return max(permission.review_override_count - overridden, 0)
        return 0
