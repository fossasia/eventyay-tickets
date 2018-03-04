import string

from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin
from pretalx.common.urls import EventUrls, build_absolute_uri


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

        role = _('organiser')
        if not self.is_orga and self.is_reviewer:
            role = _('reviewer')
        elif self.is_orga and self.is_reviewer:
            role = _('organiser and reviewer')
        if self.user:
            invitation_link = build_absolute_uri('orga:event.dashboard', event=self.event, kwargs={'event': self.event.slug})
            invitation_text = _('''Hi!
You have been added to the {event} team as a {role} - you can access the
organiser area here:

    {invitation_link}

See you there,
The {event} crew''').format(role=role, event=self.event.name, invitation_link=invitation_link)
            invitation_subject = _('You have been granted additional privileges on {event}').format(event=self.event.name)
            to = self.user.email
        else:
            self.invitation_token = get_random_string(allowed_chars=string.ascii_lowercase + string.digits, length=20)
            self.save()

            invitation_link = build_absolute_uri('orga:invitation.view', event=self.event, kwargs={'code': self.invitation_token})
            invitation_text = _('''Hi!
You have been invited to the {event} team as a {role} - Please click here to accept:

    {invitation_link}

See you there,
The {event} crew (minus you)''').format(role=role, event=self.event.name, invitation_link=invitation_link)
            invitation_subject = _('You have been invited to the {event} crew').format(event=self.event.name)
            to = self.invitation_email

        return QueuedMail(
            to=to, reply_to=self.event.email,
            subject=str(invitation_subject), text=str(invitation_text),
            event=self.event,
        )

    class urls(EventUrls):
        invitation = '/orga/invitation/{self.invitation_token}'

    def __str__(self):
        user = getattr(self.user, 'nick', self.invitation_email)
        return f'EventPermission(event={self.event.slug}, user={user}, is_orga={self.is_orga}, is_reviewer={self.is_reviewer}'
