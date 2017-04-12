import re
import string

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models


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
        verbose_name='Nickname',
        help_text='Please use only characters in the latin alphabet, plus numbers and _-.',
    )
    name = models.CharField(
        max_length=120, null=True, blank=True, verbose_name='Name',
        help_text='Please enter your real name.',
    )
    email = models.EmailField(
        verbose_name='E-Mail',
        help_text='Your email address will be used for password resets and notification about your event/submissions.',
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    send_mail = models.BooleanField(
        default=False,
        verbose_name='Receive mails from pretalx?',
    )

    pw_reset_token = models.CharField(null=True, max_length=160)
    pw_reset_time = models.DateTimeField(null=True)

    def __str__(self) -> str:
        if self.email:
            return f'{self.nick} ({self.email})'
        return self.nick

    def get_full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} '{self.nick}' {self.last_name}"
        return self.nick

    def get_short_name(self) -> str:
        return self.nick

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        return super().save(args, kwargs)
