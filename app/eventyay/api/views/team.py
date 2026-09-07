from django.db import transaction
from django.shortcuts import get_object_or_404
from django_scopes import scopes_disabled
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import exceptions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from eventyay.api.documentation import build_expand_docs, build_search_docs
from eventyay.api.mixins import PretalxViewSetMixin
from eventyay.api.serializers.team import TeamInviteSerializer, TeamSerializer
from eventyay.base.models.organizer import (
    Team,
    TeamInvite,
    TeamPermissionError,
    check_access_permissions,
)
from eventyay.base.models.auth import User


class TeamInviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()


class TeamMemberRemoveSerializer(serializers.Serializer):
    user_code = serializers.CharField()


@extend_schema_view(
    list=extend_schema(
        summary="List Teams",
        tags=["teams"],
        parameters=[
            build_search_docs("name"),
            build_expand_docs("members", "invites", "limit_tracks"),
        ],
    ),
    retrieve=extend_schema(
        summary="Show Team",
        tags=["teams"],
        parameters=[build_expand_docs("members", "invites", "limit_tracks")],
    ),
    create=extend_schema(summary="Create Team", tags=["teams"]),
    update=extend_schema(summary="Update Team", tags=["teams"]),
    partial_update=extend_schema(
        summary="Update Team (Partial Update)", tags=["teams"]
    ),
    destroy=extend_schema(summary="Delete Team", tags=["teams"]),
)
class TeamViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    queryset = Team.objects.none()
    endpoint = "teams"
    search_fields = ("name",)

    def get_queryset(self):
        queryset = (
            self.request.organizer.teams.all()
            .select_related("organizer")
            .order_by("pk")
        )
        if fields := self.check_expanded_fields("members", "limit_tracks", "invites"):
            queryset = queryset.prefetch_related(*fields)
        return queryset

    def dispatch(self, *args, **kwargs):
        with scopes_disabled():
            return super().dispatch(*args, **kwargs)

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                super().perform_update(serializer)
                check_access_permissions(self.request.organizer)
        except TeamPermissionError as e:
            raise exceptions.ValidationError(str(e))

    def perform_destroy(self, instance):
        try:
            with transaction.atomic():
                organizer = instance.organizer
                instance.logged_actions().delete()
                super().perform_destroy(instance)
                check_access_permissions(organizer)
        except TeamPermissionError as e:
            raise exceptions.ValidationError(str(e))

    @extend_schema(
        summary="Invite Member to Team",
        tags=["teams"],
        description="Creates a team invite, and sends an invite.",
        request=TeamInviteCreateSerializer,
    )
    @action(detail=True, methods=["post"])
    def invite(self, request, *args, **kwargs):
        team = self.get_object()
        input_serializer = TeamInviteCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        email = input_serializer.validated_data["email"]

        if team.members.filter(email__iexact=email).exists():
            raise exceptions.ValidationError(
                "This user is already a member of the team."
            )
        if team.invites.filter(email__iexact=email).exists():
            raise exceptions.ValidationError(
                "This user has already been invited to the team."
            )

        if team.can_change_organizer_settings:
            # Skip check if the invited email already has full-admin access
            try:
                invited_user = User.objects.get(email__iexact=email)
                already_admin = invited_user.teams.filter(
                    organizer=team.organizer, can_change_organizer_settings=True
                ).exists()
            except User.DoesNotExist:
                already_admin = TeamInvite.objects.filter(
                    team__organizer=team.organizer,
                    team__can_change_organizer_settings=True,
                    email__iexact=email,
                ).exists()

            if not already_admin:
                from eventyay.base.entitlements import check_entitlement
                current_users = User.objects.filter(
                    teams__organizer=team.organizer,
                    teams__can_change_organizer_settings=True,
                ).distinct().count()
                current_invites = TeamInvite.objects.filter(
                    team__organizer=team.organizer,
                    team__can_change_organizer_settings=True,
                ).distinct().count()
                decision = check_entitlement(
                    team.organizer,
                    'organizer.full_admins',
                    quantity=current_users + current_invites + 1,
                )
                if not decision.allowed:
                    raise exceptions.ValidationError(decision.message)

        invite = TeamInvite.objects.create(team=team, email=email)
        invite.send()

        output_serializer = TeamInviteSerializer(
            invite, context=self.get_serializer_context()
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Delete Team Invite",
        tags=["teams"],
        parameters=[
            OpenApiParameter("invite_id", OpenApiTypes.INT, OpenApiParameter.PATH)
        ],
    )
    @action(detail=True, methods=["delete"], url_path="invites/(?P<invite_id>[^/.]+)")
    def delete_invite(self, request, invite_id, *args, **kwargs):
        team = self.get_object()
        invite = get_object_or_404(TeamInvite, pk=invite_id, team=team)
        email = invite.email
        invite.delete()
        team.log_action(
            "eventyay.team.invite.orga.retract",
            person=request.user,
            orga=True,
            data={"email": email},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Remove Member from Team",
        tags=["teams"],
        request=TeamMemberRemoveSerializer,
        responses={
            204: OpenApiResponse(description="Member removed successfully."),
            400: OpenApiResponse(
                description="Member cannot be removed as it may leave events inaccessible."
            ),
        },
    )
    @action(detail=True, methods=["post"], url_path="remove_member")
    def remove_member(self, request, *args, **kwargs):
        team = self.get_object()
        input_serializer = TeamMemberRemoveSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        user_code = input_serializer.validated_data["user_code"]

        try:
            user_to_remove = User.objects.get(code=user_code)
        except User.DoesNotExist:
            raise exceptions.ValidationError("User with the specified code not found.")

        if not team.members.filter(pk=user_to_remove.pk).exists():
            raise exceptions.ValidationError("This user is not a member of this team.")

        try:
            with transaction.atomic():
                team.members.remove(user_to_remove)
                check_access_permissions(self.request.organizer)
                team.log_action(
                    "eventyay.team.remove_member",
                    person=request.user,
                    orga=True,
                    data={
                        "id": user_to_remove.id,
                        "name": user_to_remove.get_display_name(),
                        "email": user_to_remove.email,
                    },
                )
        except TeamPermissionError as e:
            raise exceptions.ValidationError(str(e))

        return Response(status=status.HTTP_204_NO_CONTENT)
