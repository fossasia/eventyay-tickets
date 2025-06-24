import logging
from http import HTTPStatus
from urllib.parse import urljoin

import jwt
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django_scopes import scopes_disabled
from pretalx_venueless.forms import VenuelessSettingsForm
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.authentication import get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from pretalx.api.documentation import build_search_docs
from pretalx.api.mixins import PretalxViewSetMixin
from pretalx.api.serializers.event import EventListSerializer, EventSerializer
from pretalx.common import exceptions
from pretalx.common.exceptions import VideoIntegrationError
from pretalx.event.models import Event
from pretalx.event.rules import get_events_for_user

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List Events", parameters=[build_search_docs("name")], tags=["events"]
    ),
    retrieve=extend_schema(summary="Show Events", tags=["events"]),
)
class EventViewSet(PretalxViewSetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = EventSerializer
    queryset = Event.objects.none()
    lookup_field = "slug"
    lookup_url_kwarg = "event"
    pagination_class = None
    permission_classes = [permissions.AllowAny]
    search_fields = ("name",)
    filterset_fields = ("is_public",)

    def get_unversioned_serializer_class(self):
        if self.action == "list":
            return EventListSerializer
        return EventSerializer

    def get_queryset(self):
        return get_events_for_user(self.request.user).order_by("-date_from")


class ConfigureVideoSettingsView(APIView):
    """
    API View to configure video settings for an event.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to configure video settings.
        @param request: request object
        @return response object
        """
        try:
            video_settings = request.data.get("video_settings")
            if not video_settings or "secret" not in video_settings:
                raise VideoIntegrationError(
                    "Video settings are missing or secret is not provided"
                )
            payload = get_payload_from_token(request, video_settings)
            event_slug = payload.get("event_slug")
            video_tokens = payload.get("video_tokens")
            with scopes_disabled():
                event_instance = Event.objects.get(slug=event_slug)
                save_video_settings_information(
                    event_slug, video_tokens, event_instance
                )
            return Response(
                {
                    "status": "success",
                    "message": "Video settings configured successfully.",
                },
                status=HTTPStatus.OK,
            )
        except Event.DoesNotExist:
            logger.error("Event does not exist.")
            raise Http404("Event does not exist")
        except ValidationError as e:
            return Response({"detail": str(e)}, status=HTTPStatus.BAD_REQUEST)
        except VideoIntegrationError as e:
            logger.error("Error configuring video settings: %s", e)
            return Response(
                {"detail": "Video settings are missing, please try after sometime."},
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
        except AuthenticationFailed as e:
            logger.error("Authentication failed: %s", e)
            raise AuthenticationFailed("Authentication failed.")


def get_payload_from_token(request, video_settings):
    """
    Verify the token and return the payload
    @param request: request object
    @param video_settings: dict containing video settings
    @return: dict containing payload data from the token
    """
    try:
        auth_header = get_authorization_header(request).split()
        if not auth_header:
            raise exceptions.AuthenticationFailedError("No authorization header")

        if len(auth_header) != 2 or auth_header[0].lower() != b"bearer":
            raise exceptions.AuthenticationFailedError(
                "Invalid token format. Must be 'Bearer <token>'"
            )

        token_decode = jwt.decode(
            auth_header[1], video_settings.get("secret"), algorithms=["HS256"]
        )

        event_slug = token_decode.get("slug")
        video_tokens = token_decode.get("video_tokens")

        if not event_slug or not video_tokens:
            raise exceptions.AuthenticationFailedError("Invalid token payload")

        return {"event_slug": event_slug, "video_tokens": video_tokens}

    except jwt.ExpiredSignatureError:
        raise exceptions.AuthenticationFailedError("Token has expired")
    except jwt.InvalidTokenError:
        raise exceptions.AuthenticationFailedError("Invalid token")


def save_video_settings_information(event_slug, video_tokens, event_instance):
    """
    Save video settings information
    @param event_slug:  A string representing the event slug
    @param video_tokens: A list of video tokens
    @param event_instance: An instance of the event
    @return: Response object
    """

    if not video_tokens:
        raise VideoIntegrationError("Video tokens list is empty")

    video_settings_data = {
        "token": video_tokens[0],
        "url": urljoin(
            settings.EVENTYAY_VIDEO_BASE_PATH, f"api/v1/worlds/{event_slug}/"
        ),
    }

    video_settings_form = VenuelessSettingsForm(
        event=event_instance, data=video_settings_data
    )

    if video_settings_form.is_valid():
        video_settings_form.save()
        logger.info("Video settings configured successfully for event %s.", event_slug)
    else:
        errors = video_settings_form.errors.get_json_data()
        formatted_errors = {
            field: [error["message"] for error in error_list]
            for field, error_list in errors.items()
        }
        logger.error(
            "Failed to configure video settings for event %s - Validation errors: %s.",
            event_slug,
            formatted_errors,
        )
        raise ValidationError(formatted_errors)
