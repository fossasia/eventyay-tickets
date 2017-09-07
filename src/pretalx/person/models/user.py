import json
import random
import re
import string

import pytz
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
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
        user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])
        return user


class User(AbstractBaseUser):
    """
    The pretalx user model: We don't really need last names and fancy stuff, so
    we stick with a nick, and optionally a name and an email address.
    """
    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'nick'

    objects = UserManager()

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
    is_superuser = models.BooleanField(default=False)
    locale = models.CharField(max_length=32, default=settings.LANGUAGE_CODE,
                              choices=settings.LANGUAGES,
                              verbose_name=_('Preferred language'))
    timezone = models.CharField(
        choices=[(tz, tz) for tz in pytz.common_timezones],
        max_length=30,
        default='UTC',
    )

    send_mail = models.BooleanField(
        default=False,
        verbose_name=_('Receive mails from pretalx?'),
    )

    pw_reset_token = models.CharField(null=True, max_length=160)
    pw_reset_time = models.DateTimeField(null=True)

    def __str__(self) -> str:
        return self.get_display_name()

    def get_full_name(self) -> str:
        if self.name:
            return f"{self.name} ('{self.nick}')"
        return self.nick

    def get_display_name(self) -> str:
        return self.name if self.name else self.nick

    def get_short_name(self) -> str:
        return self.nick

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        return super().save(args, kwargs)

    def log_action(self, action, data=None, orga=False):
        from pretalx.common.models import ActivityLog
        if data:
            data = json.dumps(data)

        ActivityLog.objects.create(
            person=self, content_object=self, action_type=action,
            data=data, is_orga_action=orga,
        )

    def logged_actions(self):
        from pretalx.common.models import ActivityLog

        return ActivityLog.objects.filter(
            content_type=ContentType.objects.get_for_model(type(self)),
            object_id=self.pk
        )

    def deactivate(self):
        from pretalx.person.models import EventPermission
        self.nick = f'deleted_user_{random.randint(0, 999)}'
        self.name = 'Deleted User'
        self.email = 'deleted@localhost'
        self.is_active = False
        self.is_superuser = False
        self.locale = 'en'
        self.timezone = 'UTC'
        self.send_mail = False
        self.pw_reset_token = None
        self.pw_reset_time = None
        self.save()

        EventPermission.objects.filter(user=self).update(is_orga=False, invitation_email=None, invitation_token=None)
