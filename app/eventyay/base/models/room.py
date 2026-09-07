import uuid
from functools import cached_property

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, JSONField, OuterRef, Q
from django.db.models.expressions import RawSQL, Value
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from i18nfield.fields import I18nCharField

from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.base.models.settings import GlobalSettings
from eventyay.base.models import OrderedModel, PretalxModel
from eventyay.base.models.auth import User
from eventyay.base.models.cache import VersionedModel
from eventyay.core.permissions import SYSTEM_ROLES, Permission
from eventyay.common.urls import EventUrls
from eventyay.talk_rules.agenda import is_agenda_visible
from eventyay.talk_rules.event import can_change_event_settings
from eventyay.talk_rules.submission import orga_can_change_submissions

from .mixins import OrderedModel, PretalxModel
from .settings import GlobalSettings


def empty_module_config():
    return []


def default_grants():
    return {
        "viewer": [],
        "participant": [],
    }


UNSCHEDULED_LINKED_SUBMISSIONS_MESSAGE = _(
    'A room with linked submissions cannot be marked as unscheduled.'
)
UNSCHEDULED_ROOM_SCHEDULING_MESSAGE = _(
    'Unscheduled rooms cannot be linked to talk sessions.'
)
DELETE_LINKED_SUBMISSIONS_MESSAGE = _(
    'This room has linked schedules/sessions. Deleting it will affect the event '
    'schedule. Please move these sessions to another room or unschedule them first.'
)
_LINKED_SUBMISSION_TALK_FILTER = {'submission__isnull': False}


def _linked_submission_talkslots(**filters):
    from eventyay.base.models.slot import TalkSlot

    return TalkSlot.objects.filter(**_LINKED_SUBMISSION_TALK_FILTER, **filters)


def room_has_linked_submissions(room) -> bool:
    """Return whether the room has scheduled talks linked to submissions."""
    from django_scopes import scope

    if 'has_linked_sessions' in room.__dict__:
        return bool(room.has_linked_sessions)
    with scope(event=room.event):
        return _linked_submission_talkslots(room=room).exists()


def linked_submission_talks(room):
    """Return one talk per session scheduled in this room.

    A session holds a slot in every schedule version it appears in, so the talks
    are deduplicated by submission to list each session once. The queryset is
    evaluated inside the event scope so that callers, such as templates, can
    iterate over the result outside of it.
    """
    from django_scopes import scope

    with scope(event=room.event):
        talks = (
            _linked_submission_talkslots(room=room)
            .select_related('submission')
            .order_by('start')
        )
        seen = set()
        unique_talks = []
        for talk in talks:
            if talk.submission_id in seen:
                continue
            seen.add(talk.submission_id)
            unique_talks.append(talk)
        return unique_talks


def validate_is_unscheduled_change(room) -> None:
    """Raise ValidationError if the room cannot be marked as unscheduled."""
    if room.pk and room_has_linked_submissions(room):
        raise ValidationError({'is_unscheduled': UNSCHEDULED_LINKED_SUBMISSIONS_MESSAGE})


def validate_talk_slot_room(room) -> None:
    """Raise ValidationError when a submission cannot be scheduled in this room."""
    if room is not None and room.is_unscheduled:
        raise ValidationError({'room': UNSCHEDULED_ROOM_SCHEDULING_MESSAGE})


def validate_talk_slot_room_from_attrs(attrs, instance) -> None:
    """Validate an incoming talk-slot room assignment (serializer layer)."""
    room = attrs.get('room', getattr(instance, 'room', None) if instance else None)
    if room and instance and instance.submission_id:
        validate_talk_slot_room(room)


def rooms_for_talk_assignment(event, *, has_submission: bool):
    """Rooms allowed when scheduling a talk slot (submissions vs breaks)."""
    if has_submission:
        return event.rooms.schedulable()
    return event.rooms.filter(deleted=False)


def validate_is_unscheduled_attrs(attrs, instance):
    """Return serializer field errors for an invalid is_unscheduled update."""
    if not attrs.get('is_unscheduled') or instance is None:
        return {}
    try:
        validate_is_unscheduled_change(instance)
    except ValidationError as exc:
        return exc.message_dict
    return {}


def partial_validated_update(serializer, body):
    """
    Run partial serializer validation and return only writable fields from body.

    Returns (validated_data, update_fields) or (None, None) when invalid.
    """
    if not serializer.is_valid():
        return None, None
    validated_data = {
        field: value
        for field, value in serializer.validated_data.items()
        if field in body
    }
    return validated_data, set(validated_data.keys())


class RoomQuerySet(models.QuerySet):
    def with_has_linked_sessions(self):
        from django_scopes import scopes_disabled

        # TalkSlot uses ScopedManager; the parent queryset is already event-scoped.
        with scopes_disabled():
            linked_talks = _linked_submission_talkslots(
                room_id=OuterRef('pk'),
                schedule__event_id=OuterRef('event_id'),
            )
        return self.annotate(has_linked_sessions=Exists(linked_talks))

    def schedulable(self):
        """Rooms that may receive talk slots in the schedule."""
        return self.filter(deleted=False, is_unscheduled=False)

    def with_permission(
        self, *, user=None, traits=None, event, permission=Permission.ROOM_VIEW
    ):
        from .auth import RoomGrant, EventGrant

        # Normalize traits input
        # - If traits is explicitly provided, use it; otherwise, read from user when available
        # - Always coerce to a simple list[str] for proper DB array parameterization
        if traits is None:
            if user is not None:
                traits = user.traits
            else:
                traits = []

        allow_empty_traits = not user or user.type == User.UserType.PERSON

        # Ensure traits is always a proper list of strings for SQL parameterization
        if isinstance(traits, str):
            # Accept legacy "(a,b,c)" string format by parsing it into a list
            traits = [t.strip() for t in traits.strip("()").split(",") if t.strip()]
        else:
            try:
                # Convert any iterable (set/tuple/queryset) to a list of strings
                traits = [str(t) for t in list(traits or [])]
            except TypeError:
                # Non-iterables (shouldn't happen) fallback to empty list
                traits = []

        if event.has_permission_implicit(
            traits=traits,
            permissions=[permission],
            allow_empty_traits=allow_empty_traits,
        ):
            # User has the permission globally, nothing to do
            return self.all()

        # Get all roles that grant view access
        roles = [
            role
            for role, permissions in [
                *event.roles.items(),
                *SYSTEM_ROLES.items(),
            ]
            if permission.value in permissions
        ]

        if not roles:  # pragma: no cover
            # No role grants access, impossible
            return self.none()

        if user:
            sq_user_has_room_grant = RoomGrant.objects.filter(
                user=user, event=event, room_id=OuterRef("pk"), role__in=roles
            )
            sq_user_has_event_grant = EventGrant.objects.filter(
                user=user, event=event, role__in=roles
            )
            qs = self.annotate(
                user_has_room_grant=Exists(sq_user_has_room_grant),
                user_has_event_grant=Exists(sq_user_has_event_grant),
            )
            requirements = Q(user_has_room_grant=True) | Q(user_has_event_grant=True)
        else:
            qs = self
            requirements = Q()

        # Implicit role grants, i.e. grants given by trait_grants values on the room itself
        # We calculate this entirely in SQL for performance reasons. This is a little more complicated
        # since trait_grants can contain AND and OR restrictions.
        # For example, if we know from above the "moderator" role would grant the required permission, we need to
        # check the trait_grants["moderator"] value of the room, which always is an array. All values inside the
        # array are connected as AND restrictions. However, the value may either be strings (user must have that trait)
        # or arrays (user must have one of the traits -- OR). We therefore need to do In-SQL type checks.
        # In case it is an empty array, everyone is permitted, unless allow_empty_traits is set to False.
        # When our user has traits, this is automatically ensured by the ALL() statement, but when traits=[] we
        # need to do a special case check since "IN ()" is not valid SQL
        for i, role in enumerate(roles):
            if traits and len(traits) > 0:
                ext = ""
                ext_args = []
                if not allow_empty_traits:
                    ext = " AND jsonb_array_length(trait_grants->%s) > 0"
                    ext_args.append(role)

                qs = qs.annotate(
                    **{
                        f"has_role_{i}": RawSQL(
                            f"""(
                            trait_grants ? %s AND
                            trait_grants->%s IS NOT NULL AND
                            TRUE = ALL(
                                SELECT (
                                    CASE jsonb_typeof(d{i}.elem)
                                        WHEN 'array' THEN EXISTS(SELECT 1 FROM jsonb_array_elements(d{i}.elem) e{i}(elem) WHERE e{i}.elem#>>'{{}}' = ANY(%s::text[]) )
                                        ELSE d{i}.elem#>>'{{}}' = ANY(%s::text[])
                                    END
                                ) FROM jsonb_array_elements( trait_grants->%s ) AS d{i}(elem)
                            ) {ext}
                        )""",
                            (
                                role,  # ? check
                                role,  # IS NOT NULL check
                                traits,  # = ANY check (array for first case)
                                traits,  # = ANY check (array for second case)
                                role,  # jsonb_array_elements
                                *ext_args,
                            ),
                        )
                    }
                )
            elif not allow_empty_traits:
                qs = qs.annotate(**{f"has_role_{i}": Value(False)})
            else:
                qs = qs.annotate(
                    **{
                        f"has_role_{i}": RawSQL(
                            """(
                                trait_grants ? %s AND
                                trait_grants->%s IS NOT NULL AND
                                jsonb_array_length(trait_grants->%s) = 0
                            )""",
                            (
                                role,  # ? check
                                role,  # IS NOT NULL check
                                role,  # jsonb_array_length
                            ),
                        )
                    }
                )
            requirements |= Q(**{f"has_role_{i}": True})

        return qs.filter(requirements, event=event)


class Room(VersionedModel, OrderedModel, PretalxModel):
    """A Room is an actual place where talks will be scheduled.

    The Room object stores some meta information. Most, like capacity,
    are not in use right now.
    """

    log_prefix = "eventyay.room"

    deleted = models.BooleanField(default=False)
    description = I18nCharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('A description for attendees, for example directions.'),
    )
    event = models.ForeignKey(to='Event', on_delete=models.PROTECT, related_name='rooms')
    name = I18nCharField(max_length=100, verbose_name=_('Name'))
    guid = models.UUIDField(
        null=True,
        blank=True,
        verbose_name=_('GUID'),
        help_text=_('Unique identifier (UUID) to help external tools identify the room.'),
    )
    speaker_info = I18nCharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_('Speaker Information'),
        help_text=_(
            'Information relevant for speakers scheduled in this room, for example room size, special directions, '
            'available adaptors for video input …'
        ),
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Capacity'),
        help_text=_('How many people can fit in the room?'),
    )
    position = models.PositiveIntegerField(null=True, blank=True)

    # Video/interactive platform fields
    trait_grants = JSONField(null=True, blank=True, default=default_grants)
    module_config = JSONField(null=True, default=empty_module_config)
    picture = models.FileField(null=True, blank=True)
    sorting_priority = models.IntegerField(default=0)
    import_id = models.CharField(max_length=100, null=True, blank=True)
    pretalx_id = models.IntegerField(default=0)
    schedule_data = JSONField(null=True, blank=True)
    force_join = models.BooleanField(default=False)
    is_unscheduled = models.BooleanField(
        default=False,
        verbose_name=_('Unscheduled room'),
        help_text=_('If enabled, this room will not appear in the schedule or schedule-editor and cannot be linked to talk sessions.')
    )

    objects = RoomQuerySet.as_manager()

    class Meta:
        ordering = ('position',)
        unique_together = ('event', 'guid')
        rules_permissions = {
            'list': is_agenda_visible | orga_can_change_submissions,
            'view': is_agenda_visible | orga_can_change_submissions,
            'orga_list': orga_can_change_submissions,
            'orga_view': orga_can_change_submissions,
            'create': can_change_event_settings,
            'update': can_change_event_settings,
            'delete': can_change_event_settings,
        }

    class urls(EventUrls):
        """URL patterns for room views."""
        settings_base = edit = '{self.event.orga_urls.room_settings}{self.pk}/'
        delete = '{settings_base}delete/'

    def __str__(self) -> str:
        return str(self.name)

    def clean(self):
        super().clean()
        if self.is_unscheduled:
            validate_is_unscheduled_change(self)

    @property
    def log_parent(self):
        return self.event

    @staticmethod
    def get_order_queryset(event):
        return event.rooms.all()

    @cached_property
    def uuid(self):
        """Either a UUID5 calculated from the submission code and the instance identifier;
        or GUID value of the room, if it was imported or set manually."""
        if self.guid:
            return self.guid
        if not self.pk:
            return ''

        return uuid.uuid5(GlobalSettings().get_instance_identifier(), f'room:{self.pk}')

    @property
    def slug(self) -> str:
        """The slug makes tracks more readable in URLs.
        It consists of the ID, followed by a slugified (and, in lookups,
        optional) form of the track name.
        """
        return f'{self.id}-{slugify(self.name)}'

    @property
    def has_interpretation(self) -> bool:
        if getattr(self, 'interpretation_use_plugin_streams', False):
            return True
        if hasattr(self, 'interpretation_language_streams') and self.interpretation_language_streams:
            return True
        if hasattr(self, 'interpretation_config') and getattr(self.interpretation_config, 'language_streams', None):
            return True
        return False

    def get_current_stream(self, at_time=None):
        """Get the currently active stream schedule for this room."""
        from django.utils.timezone import now

        from .stream_schedule import StreamSchedule

        at_time = at_time or now()

        return (
            StreamSchedule.objects.filter(
                room=self, start_time__lte=at_time, end_time__gt=at_time
            )
            .order_by('start_time')
            .first()
        )

    def get_next_stream(self, at_time=None):
        """Get the next upcoming stream schedule for this room."""
        from django.utils.timezone import now

        from .stream_schedule import StreamSchedule

        at_time = at_time or now()

        return (
            StreamSchedule.objects.filter(
                room=self, start_time__gt=at_time
            )
            .order_by('start_time')
            .first()
        )


@receiver(post_save, sender=Room)
@receiver(post_delete, sender=Room)
def invalidate_schedule_cache_on_room_change(sender, instance, **kwargs):
    from eventyay.base.services.stale_cache import bump_schedule_cache_version_on_commit

    event_id = instance.event_id
    if event_id:
        bump_schedule_cache_version_on_commit(event_id)


class Reaction(models.Model):
    room = models.ForeignKey("Room", related_name="reactions", on_delete=models.CASCADE)
    datetime = models.DateTimeField(auto_now_add=True)
    reaction = models.CharField(max_length=100)
    amount = models.IntegerField()


class RoomView(models.Model):
    room = models.ForeignKey(to="Room", related_name="views", on_delete=models.CASCADE)
    start = models.DateTimeField(
        auto_now_add=True,
    )
    end = models.DateTimeField(
        null=True, db_index=True
    )  # index required for control/ dashboard
    user = models.ForeignKey(to="user", related_name="views", on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=["start"]),
        ]


def get_room_with_linked_sessions(room):
    """Return the room annotated with has_linked_sessions when possible."""
    from django_scopes import scope

    with scope(event=room.event):
        annotated = (
            room.event.rooms.filter(pk=room.pk).with_has_linked_sessions().first()
        )
    return annotated or room


class RoomLinkedSessionsSerializerMixin(serializers.Serializer):
    """DRF mixin; must subclass Serializer so SerializerMethodField is registered."""

    has_linked_sessions = serializers.SerializerMethodField(read_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        errors = validate_is_unscheduled_attrs(attrs, self.instance)
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_has_linked_sessions(self, obj):
        return room_has_linked_submissions(obj)


class RoomConfigSerializer(RoomLinkedSessionsSerializerMixin, I18nAwareModelSerializer):
    class Meta:
        model = Room
        fields = (
            "id",
            "trait_grants",
            "module_config",
            "picture",
            "name",
            "description",
            "sorting_priority",
            "pretalx_id",
            "force_join",
            "schedule_data",
            "is_unscheduled",
            "has_linked_sessions",
        )


def approximate_view_number(actual_number):
    if actual_number is None or actual_number < 1:
        return "none"
    elif actual_number > 10:
        return "many"
    else:
        return "few"


def generate_short_token():
    chars = "abcdefghijklmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ123456789"
    return get_random_string(6, chars)


class AnonymousInvite(models.Model):
    short_token = models.CharField(
        db_index=True,
        unique=True,
        default=generate_short_token,
        max_length=150,
    )
    event = models.ForeignKey(
        "base.Event", related_name="anonymous_invites", on_delete=models.CASCADE
    )
    room = models.ForeignKey(
        "Room", related_name="anonymous_invites", on_delete=models.CASCADE
    )
    expires = models.DateTimeField()
