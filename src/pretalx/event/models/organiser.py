import string

from django.core.validators import RegexValidator
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField

from pretalx.common.mixins import LogMixin
from pretalx.common.urls import EventUrls, build_absolute_uri
from pretalx.person.models import User

SLUG_CHARS = 'a-zA-Z0-9.-'


class Organiser(LogMixin, models.Model):
    """The Organiser model represents the entity responsible for one or several events."""

    name = I18nCharField(max_length=190, verbose_name=_('Name'))
    slug = models.SlugField(
        max_length=50,
        db_index=True,
        unique=True,
        validators=[
            RegexValidator(
                regex=f"^[{SLUG_CHARS}]+$",
                message=_(
                    'The slug may only contain letters, numbers, dots and dashes.'
                ),
            )
        ],
        verbose_name=_('Short form'),
        help_text=_(
            'Should be short, only contain lowercase letters and numbers, and must be unique, as it is used in URLs.'
        ),
    )

    def __str__(self) -> str:
        """Used in generated forms."""
        return str(self.name)

    class orga_urls(EventUrls):
        base = '/orga/organiser/{self.slug}'
        teams = '{base}/teams'
        new_team = '{teams}/new'


class Team(LogMixin, models.Model):
    """Team members share permissions for one or several events of one organiser."""

    organiser = models.ForeignKey(
        to=Organiser, related_name='teams', on_delete=models.CASCADE
    )
    name = models.CharField(max_length=190, verbose_name=_("Team name"))
    members = models.ManyToManyField(
        to=User, related_name='teams', verbose_name=_('Team members')
    )
    all_events = models.BooleanField(
        default=False, verbose_name=_('All events (including newly created ones)')
    )
    limit_events = models.ManyToManyField(
        to='Event', verbose_name=_('Limit to events'), blank=True
    )
    can_create_events = models.BooleanField(
        default=False, verbose_name=_('Can create events')
    )
    can_change_teams = models.BooleanField(
        default=False, verbose_name=_('Can change teams and permissions')
    )
    can_change_organiser_settings = models.BooleanField(
        default=False, verbose_name=_('Can change organiser settings')
    )
    can_change_event_settings = models.BooleanField(
        default=False, verbose_name=_('Can change event settings')
    )
    can_change_submissions = models.BooleanField(
        default=False, verbose_name=_('Can work with and change submissions')
    )
    is_reviewer = models.BooleanField(default=False, verbose_name=_('Is a reviewer'))
    review_override_votes = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Override votes'),
        help_text=_(
            'Each member of this team will have this amount of override votes per event to indicate an absolute positive or negative opinion of a submission.'
        ),
    )

    def __str__(self) -> str:
        """Help with debugging."""
        return _('{name} on {orga}').format(
            name=str(self.name), orga=str(self.organiser)
        )

    @cached_property
    def permission_set(self) -> set:
        attribs = dir(self)
        return {
            a
            for a in attribs
            if (a.startswith('can_') or a.startswith('is_'))
            and getattr(self, a, False) is True
        }


def generate_invite_token():
    return get_random_string(
        allowed_chars=string.ascii_lowercase + string.digits, length=32
    )


class TeamInvite(models.Model):
    """A TeamInvite is someone who has been invited to a team but hasn't accept the invitation yet."""

    team = models.ForeignKey(to=Team, related_name='invites', on_delete=models.CASCADE)
    email = models.EmailField(null=True, blank=True, verbose_name=_('Email'))
    token = models.CharField(
        default=generate_invite_token, max_length=64, null=True, blank=True
    )

    def __str__(self) -> str:
        """Help with debugging."""
        return _('Invite to team {team} for {email}').format(
            team=str(self.team), email=self.email
        )

    class urls(EventUrls):
        invitation = '/orga/invitation/{self.token}'

    def send(self, event):
        from pretalx.mail.models import QueuedMail

        invitation_link = build_absolute_uri(
            'orga:invitation.view', kwargs={'code': self.token}
        )
        invitation_text = _(
            '''Hi!
You have been invited to the {name} event organiser team - Please click here to accept:

{invitation_link}

See you there,
The {event} team'''
        ).format(
            name=str(self.team.name),
            invitation_link=invitation_link,
            event=str(event.name) if event else str(self.team.organiser.name),
        )
        invitation_subject = _('You have been invited to an organiser team')

        mail = QueuedMail(
            to=self.email,
            event=event,
            subject=str(invitation_subject),
            text=str(invitation_text),
        )
        if event:
            mail.save()
        else:
            mail.send()
        return mail
