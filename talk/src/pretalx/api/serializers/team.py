from rest_flex_fields.serializers import FlexFieldsSerializerMixin
from rest_framework import exceptions, serializers

from pretalx.api.mixins import PretalxSerializer
from pretalx.api.versions import CURRENT_VERSIONS, register_serializer
from pretalx.event.models import Event, Team, TeamInvite
from pretalx.person.models import User
from pretalx.submission.models import Track


@register_serializer(versions=CURRENT_VERSIONS)
class TeamMemberSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    class Meta:
        model = User
        fields = (
            "code",
            "name",
            "email",
        )


@register_serializer(versions=CURRENT_VERSIONS)
class TeamInviteSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    class Meta:
        model = TeamInvite
        fields = (
            "id",
            "email",
            "token",
        )


@register_serializer(versions=CURRENT_VERSIONS)
class TeamSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    limit_events = serializers.SlugRelatedField(
        slug_field="slug", many=True, queryset=Event.objects.none(), required=False
    )
    limit_tracks = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Track.objects.none(), required=False
    )
    members = serializers.SlugRelatedField(
        slug_field="code", many=True, required=False, queryset=User.objects.none()
    )
    invites = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=TeamInvite.objects.none()
    )

    class Meta:
        model = Team
        fields = (
            "id",
            "name",
            "members",
            "invites",
            "all_events",
            "limit_events",
            "limit_tracks",
            "can_create_events",
            "can_change_teams",
            "can_change_organiser_settings",
            "can_change_event_settings",
            "can_change_submissions",
            "is_reviewer",
            "force_hide_speaker_names",
        )
        expandable_fields = {
            "limit_tracks": (
                "pretalx.api.serializers.submission.TrackSerializer",
                {"many": True},
            ),
            "members": (TeamMemberSerializer, {"many": True, "required": False}),
            "invites": (TeamInviteSerializer, {"many": True, "required": False}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = kwargs.get("context", {}).get("request")
        if request and hasattr(request, "organiser"):
            self.fields["limit_events"].queryset = request.organiser.events.all()
            self.fields["limit_tracks"].queryset = Track.objects.filter(
                event__organiser=request.organiser
            )
            self.fields["invites"].queryset = TeamInvite.objects.filter(
                team__organiser=request.organiser
            )
        if self.instance and not isinstance(self.instance, list) and self.instance.pk:
            self.fields["limit_events"].queryset = Track.objects.filter(
                event__in=self.instance.events.all()
            )
            self.fields["members"].queryset = self.instance.members.all()

    def validate(self, data):
        all_events = self.get_with_fallback(data, "all_events")
        limit_events = self.get_with_fallback(data, "limit_events")
        if not all_events and not limit_events:
            raise exceptions.ValidationError(
                "Please either pick some events for this team, or grant access to all your events!"
            )
        permissions = (
            "can_create_events",
            "can_change_teams",
            "can_change_organiser_settings",
            "can_change_event_settings",
            "can_change_submissions",
            "is_reviewer",
        )
        if not any(
            self.get_with_fallback(data, permission) for permission in permissions
        ):
            raise exceptions.ValidationError(
                "Please pick at least one permission for this team!"
            )
        return data

    def create(self, validated_data):
        validated_data["organiser"] = getattr(
            self.context.get("request"), "organiser", None
        )
        return super().create(validated_data)
