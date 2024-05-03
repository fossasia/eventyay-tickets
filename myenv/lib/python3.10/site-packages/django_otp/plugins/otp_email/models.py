from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.mail import send_mail
from django.db import models
from django.template import Context, Template
from django.template.loader import get_template
from django.utils.translation import gettext

from django_otp.models import (
    CooldownMixin,
    GenerateNotAllowed,
    SideChannelDevice,
    ThrottlingMixin,
    TimestampMixin,
)
from django_otp.util import hex_validator, random_hex

from .conf import settings


def default_key():  # pragma: no cover
    """Obsolete code here for migrations."""
    return random_hex(20)


def key_validator(value):  # pragma: no cover
    """Obsolete code here for migrations."""
    return hex_validator()(value)


class EmailDevice(TimestampMixin, CooldownMixin, ThrottlingMixin, SideChannelDevice):
    """
    A :class:`~django_otp.models.SideChannelDevice` that delivers a token to
    the email address saved in this object or alternatively to the user's
    registered email address (``user.email``).

    The tokens are valid for :setting:`OTP_EMAIL_TOKEN_VALIDITY` seconds. Once
    a token has been accepted, it is no longer valid.

    Note that if you allow users to reset their passwords by email, this may
    provide little additional account security. It may still be useful for,
    e.g., requiring the user to re-verify their email address on new devices.

    .. attribute:: email

        *EmailField*: An alternative email address to send the tokens to.

    """

    email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
        help_text='Optional alternative email address to send tokens to',
    )

    def generate_challenge(self, extra_context=None):
        """
        Generates a random token and emails it to the user.

        :param extra_context: Additional context variables for rendering the
            email template.
        :type extra_context: dict

        """
        generate_allowed, data_dict = self.generate_is_allowed()
        if generate_allowed:
            message = self._deliver_token(extra_context)
        else:
            if data_dict['reason'] == GenerateNotAllowed.COOLDOWN_DURATION_PENDING:
                next_generation_naturaltime = naturaltime(
                    data_dict['next_generation_at']
                )
                message = (
                    "Token generation cooldown period has not expired yet. Next"
                    f" generation allowed {next_generation_naturaltime}."
                )
            else:
                message = "Token generation is not allowed at this time"

        return message

    def _deliver_token(self, extra_context):
        self.cooldown_set(commit=False)
        self.generate_token(valid_secs=settings.OTP_EMAIL_TOKEN_VALIDITY, commit=True)

        context = {'token': self.token, **(extra_context or {})}
        if settings.OTP_EMAIL_BODY_TEMPLATE:
            body = Template(settings.OTP_EMAIL_BODY_TEMPLATE).render(Context(context))
        else:
            body = get_template(settings.OTP_EMAIL_BODY_TEMPLATE_PATH).render(context)

        if settings.OTP_EMAIL_BODY_HTML_TEMPLATE:
            body_html = Template(settings.OTP_EMAIL_BODY_HTML_TEMPLATE).render(
                Context(context)
            )
        elif settings.OTP_EMAIL_BODY_HTML_TEMPLATE_PATH:
            body_html = get_template(settings.OTP_EMAIL_BODY_HTML_TEMPLATE_PATH).render(
                context
            )
        else:
            body_html = None

        self.send_mail(body, html_message=body_html)

        message = gettext("sent by email")

        return message

    def send_mail(self, body, **kwargs):
        """
        A simple wrapper for :func:`django.core.mail.send_mail`.

        Subclasses (e.g. proxy models) may override this to customize delivery.

        """
        send_mail(
            str(settings.OTP_EMAIL_SUBJECT),
            body,
            settings.OTP_EMAIL_SENDER,
            [self.email or self.user.email],
            **kwargs,
        )

    def verify_token(self, token):
        """"""
        verify_allowed, _ = self.verify_is_allowed()
        if verify_allowed:
            verified = super().verify_token(token)

            if verified:
                self.throttle_reset(commit=False)
                self.set_last_used_timestamp(commit=False)
                self.save()
            else:
                self.throttle_increment()
        else:
            verified = False

        return verified

    def get_cooldown_duration(self):
        """
        Returns :setting:`OTP_EMAIL_COOLDOWN_DURATION`.
        """
        return settings.OTP_EMAIL_COOLDOWN_DURATION

    def get_throttle_factor(self):
        """
        Returns :setting:`OTP_EMAIL_THROTTLE_FACTOR`.
        """
        return settings.OTP_EMAIL_THROTTLE_FACTOR
