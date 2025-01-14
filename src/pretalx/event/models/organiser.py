import json
import string

from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from django_scopes import scope
from i18nfield.fields import I18nCharField

from pretalx.common.models.mixins import PretalxModel
from pretalx.common.urls import EventUrls, build_absolute_uri
from pretalx.event.models.event import FULL_SLUG_REGEX
from pretalx.person.models import User


def check_access_permissions(organiser):
    """We run this method when team permissions are changed, inside a transaction.

    We need to make sure that after the change is made, there is still somebody who has
    administrator access to every event and the organiser itself.
    """
    warnings = []
    teams = (
        organiser.teams.all()
        .annotate(member_count=models.Count("members"))
        .filter(member_count__gt=0)
    )
    if not [t for t in teams if t.can_change_teams]:
        raise Exception(
            _(
                "There must be at least one team with the permission to change teams, as otherwise nobody can create new teams or grant permissions to existing teams."
            )
        )
    if not [t for t in teams if t.can_create_events]:
        warnings.append(
            (
                "no_can_create_events",
                _("Nobody on your teams has the permission to create new events."),
            )
        )
    if not [t for t in teams if t.can_change_organiser_settings]:
        warnings.append(
            (
                "no_can_change_organiser_settings",
                _(
                    "Nobody on your teams has the permission to change organiser-level settings."
                ),
            )
        )

    for event in organiser.events.all():
        event_teams = (
            event.teams.all()
            .annotate(member_count=models.Count("members"))
            .filter(member_count__gt=0)
        )
        if not event_teams:
            raise Exception(
                str(
                    _(
                        "There must be at least one team with access to every event. Currently, nobody has access to {event_name}."
                    )
                ).format(event_name=event.name)
            )
        if not [t for t in event_teams if t.can_change_event_settings]:
            warnings.append(
                (
                    "no_can_cange_event_settings",
                    str(
                        _(
                            "Nobody on your teams has the permissions to change settings for the event {event_name}"
                        )
                    ).format(event_name=event.name),
                )
            )
    return warnings


class Organiser(PretalxModel):
    """The Organiser model represents the entity responsible for at least one.

    :class:`~pretalx.event.models.event.Event`.
    """

    name = I18nCharField(max_length=190, verbose_name=_("Name"))
    slug = models.SlugField(
        max_length=50,
        db_index=True,
        unique=True,
        validators=[
            RegexValidator(
                regex=FULL_SLUG_REGEX,
                message=_(
                    "The slug may only contain letters, numbers, dots and dashes."
                ),
            )
        ],
        verbose_name=_("Short form"),
        help_text=_(
            "Should be short, only contain lowercase letters and numbers, and must be unique, as it is used in URLs."
        ),
    )

    objects = models.Manager()

    def __str__(self) -> str:
        """Used in generated forms."""
        return str(self.name)

    class orga_urls(EventUrls):
        base = "/orga/organiser/{self.slug}/"
        settings = "/orga/organiser/{self.slug}/settings/"
        delete = "{settings}delete"
        teams = "{base}teams/"
        new_team = "{teams}new"
        user_search = "{base}api/users"

    @transaction.atomic
    def shred(self, person=None):
        """Irrevocably deletes the organiser and all related events and their
        data."""
        from pretalx.common.models import ActivityLog

        ActivityLog.objects.create(
            person=person,
            action_type="pretalx.organiser.delete",
            content_object=self,
            is_orga_action=True,
            data=json.dumps(
                {
                    "slug": self.slug,
                    "name": str(self.name),
                }
            ),
        )
        for event in self.events.all():
            with scope(event=event):
                event.shred(person=person)
        # We keep our logged actions, even with the now-broken content type
        self.delete()

    shred.alters_data = True


class Team(PretalxModel):
    """A team is a group of people working for the same organiser.

    Team members (of type :class:`~pretalx.person.models.user.User`) share
    permissions for one or several events of
    :class:`~pretalx.event.models.organiser.Organiser`.  People can be in
    multiple Teams, and will have all permissions *any* of their teams has.
    """

    organiser = models.ForeignKey(
        to=Organiser, related_name="teams", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=190, verbose_name=_("Team name"))
    members = models.ManyToManyField(
        to=User, related_name="teams", verbose_name=_("Team members")
    )
    all_events = models.BooleanField(
        default=False,
        verbose_name=_(
            "Apply permissions to all events by this organiser (including newly created ones)"
        ),
    )
    limit_events = models.ManyToManyField(
        to="Event", verbose_name=_("Limit permissions to these events"), blank=True
    )
    limit_tracks = models.ManyToManyField(
        to="submission.Track", verbose_name=_("Limit to tracks"), blank=True
    )
    can_create_events = models.BooleanField(
        default=False, verbose_name=_("Can create events")
    )
    can_change_teams = models.BooleanField(
        default=False, verbose_name=_("Can change teams and permissions")
    )
    can_change_organiser_settings = models.BooleanField(
        default=False, verbose_name=_("Can change organiser settings")
    )
    can_change_event_settings = models.BooleanField(
        default=False, verbose_name=_("Can change event settings")
    )
    can_change_submissions = models.BooleanField(
        default=False, verbose_name=_("Can work with and change proposals")
    )
    is_reviewer = models.BooleanField(default=False, verbose_name=_("Is a reviewer"))
    force_hide_speaker_names = models.BooleanField(
        verbose_name=_("Always hide speaker names"),
        help_text=_(
            "Normally, anonymisation is configured in the event review settings. "
            "This setting will <b>override the event settings</b> and always hide speaker names for this team."
        ),
        default=False,
    )

    objects = models.Manager()

    def __str__(self) -> str:
        """Help with debugging."""
        return _("{name} on {orga}").format(
            name=str(self.name), orga=str(self.organiser)
        )

    @cached_property
    def permission_set(self) -> set:
        """A set of all permissions this team has, as strings."""
        attribs = dir(self)
        return {
            attr
            for attr in attribs
            if (attr.startswith("can_") or attr.startswith("is_"))
            and getattr(self, attr, False) is True
        }

    @cached_property
    def permission_set_display(self) -> set:
        """The same as :meth:`permission_set`, but with human-readable names."""
        return {
            getattr(self._meta.get_field(attr), "verbose_name", None) or attr
            for attr in self.permission_set
        }

    @cached_property
    def events(self):
        if self.all_events:
            return self.organiser.events.all()
        return self.limit_events.all()

    class orga_urls(EventUrls):
        base = "{self.organiser.orga_urls.teams}{self.pk}/"
        delete = "{base}delete"


def generate_invite_token():
    return get_random_string(
        allowed_chars=string.ascii_lowercase + string.digits, length=32
    )


class TeamInvite(PretalxModel):
    """A TeamInvite is someone who has been invited to a team but hasn't accept
    the invitation yet."""

    team = models.ForeignKey(to=Team, related_name="invites", on_delete=models.CASCADE)
    email = models.EmailField(null=True, blank=True, verbose_name=_("Email"))
    token = models.CharField(
        default=generate_invite_token, max_length=64, null=True, blank=True
    )

    objects = models.Manager()

    def __str__(self) -> str:
        """Help with debugging."""
        return _("Invite to team {team} for {email}").format(
            team=str(self.team), email=self.email
        )

    class urls(EventUrls):
        invitation = "/orga/invitation/{self.token}"

    def send(self):
        from pretalx.mail.models import QueuedMail

        invitation_link = build_absolute_uri(
            "orga:invitation.view", kwargs={"code": self.token}
        )
        invitation_text = _(
            """Hi!
You have been invited to the {name} event organiser team - Please click here to accept:

{invitation_link}

See you there,
The {organiser} team"""
        ).format(
            name=str(self.team.name),
            invitation_link=invitation_link,
            organiser=str(self.team.organiser.name),
        )
        invitation_subject = _("You have been invited to an organiser team")

        mail = QueuedMail.objects.create(
            to=self.email,
            subject=str(invitation_subject),
            text=str(invitation_text),
            locale=get_language(),
        )
        mail.send()
        return mail

    send.alters_data = True
