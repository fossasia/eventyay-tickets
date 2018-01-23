import string

from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin
from pretalx.common.urls import build_absolute_uri


class EventPermission(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='permissions',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        to='person.User',
        related_name='permissions',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    is_orga = models.BooleanField(
        default=True,
        verbose_name=_('Organizes the event'),
    )
    is_reviewer = models.BooleanField(
        default=False,
        verbose_name=_('May write reviews for this event'),
    )
    review_override_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Override votes for reviews'),
        help_text=_('How many times may this user cast an overriding votes or vetos?'),
    )
    invitation_token = models.CharField(
        max_length=255,
        null=True, blank=True,
    )
    invitation_email = models.EmailField(
        null=True, blank=True,
    )

    def send_invite_email(self):
        from pretalx.mail.models import QueuedMail

        self.invitation_token = get_random_string(allowed_chars=string.ascii_lowercase + string.digits, length=20)
        self.save()

        invitation_link = build_absolute_uri('orga:invitation.view', event=self.event, kwargs={'code': self.invitation_token})

        if self.is_orga and not self.is_reviewer:
            team = _('organiser')
        elif self.is_orga and not self.is_reviewer:
            team = _('reviewer')
        elif self.is_orga and self.is_reviewer:
            role = _('organiser and reviewer')

        invitation_text = _('''Hi!
You have been invited to the {event} team as a {role} - Please click here to accept:

    {invitation_link}

See you there,
The {event} crew (minus you)''').format(role=role, event=self.event.name, invitation_link=invitation_link)
        invitation_subject = _('You have been invited to the {event} crew').format(event=self.event.name)

        return QueuedMail(
            to=self.invitation_email, reply_to=self.event.email,
            subject=str(invitation_subject), text=str(invitation_text),
            event=self.event,
        )

    def __str__(self):
        return '{} on {}'.format(self.user, self.event)
