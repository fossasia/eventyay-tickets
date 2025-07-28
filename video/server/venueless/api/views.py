import json
import logging
from contextlib import suppress
from urllib.parse import urlparse

import jwt
import requests
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from rest_framework import exceptions, viewsets
from rest_framework.authentication import get_authorization_header
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from eventyay.base.api.auth import (
    ApiAccessRequiredPermission,
    RoomPermissions,
    UserDeletePermissions,
    EventPermissions,
)
from eventyay.api.serializers.rooms import RoomSerializer, EventSerializer
from eventyay.base.models import Channel, User
from eventyay.base.services.event import notify_schedule_change, notify_event_change

from eventyay.base.models.event import Event
from eventyay.base.models.room import Room
from .task import configure_video_settings_for_talks
from .utils import get_protocol

logger = logging.getLogger(__name__)


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.none()
    serializer_class = RoomSerializer
    permission_classes = [ApiAccessRequiredPermission & RoomPermissions]

    def get_queryset(self):
        return self.request.event.rooms.with_permission(
            traits=self.request.auth.get("traits"), event=self.request.event
        )

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        for m in serializer.instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.get_or_create(
                    room=serializer.instance, event=self.request.event
                )
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(self.request.event.id)
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        for m in serializer.instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.get_or_create(
                    room=serializer.instance, event=self.request.event
                )
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(self.request.event.id)
        )

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        for m in instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.filter(room=instance, event=self.request.event).delete()
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(self.request.event.id)
        )


class EventView(APIView):
    permission_classes = [ApiAccessRequiredPermission & EventPermissions]

    def get(self, request, **kwargs):
        return Response(EventSerializer(request.event).data)

    @transaction.atomic
    def patch(self, request, **kwargs):
        serializer = EventSerializer(request.event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(request.event.id)
        )
        return Response(serializer.data)


class EventThemeView(APIView):
    permission_classes = []

    def get(self, request, **kwargs):
        """
        Retrieve theme config of an event
        @param request: request obj
        @param kwargs: event_id
        @return: theme data of an event
        """
        try:
            event = get_object_or_404(Event, id=kwargs["event_id"])
            return Response(EventSerializer(event).data["config"]["theme"])
        except KeyError:
            logger.error(
                "error happened when trying to get theme data of event: %s",
                kwargs["event_id"],
            )
            return Response(
                "error happened when trying to get theme data of event: "
                + kwargs["event_id"],
                status=503,
            )


class CreateEventView(APIView):
    authentication_classes = []  # disables authentication
    permission_classes = []

    @staticmethod
    def post(request, *args, **kwargs) -> JsonResponse:
        payload = CreateEventView.get_payload_from_token(request)

        # check if user has permission to create event
        if payload.get("has_permission"):
            secret = get_random_string(length=64)
            config = {
                "JWT_secrets": [
                    {
                        "issuer": "any",
                        "audience": "eventyay",
                        "secret": secret,
                    }
                ]
            }

            titles = request.data.get("title") or {}
            locale = request.data.get("locale")

            title_values = [value for value in titles.values() if value]
            title_default = title_values[0] if title_values else ""

            title = titles.get(locale) or titles.get("en") or title_default

            attendee_trait_grants = request.data.get("traits", {}).get("attendee", "")
            if not isinstance(attendee_trait_grants, str):
                raise ValidationError("Attendee traits must be a string")

            trait_grants = {
                "admin": ["admin"],
                "attendee": (
                    [attendee_trait_grants] if attendee_trait_grants else ["attendee"]
                ),
                "scheduleuser": ["schedule-update"],
            }

            # if event already exists, update it, otherwise create a new event
            event_id = request.data.get("id")
            domain_path = "{}{}/{}".format(
                settings.DOMAIN_PATH,
                settings.BASE_PATH,
                request.data.get("id"),
            )
            try:
                if not event_id:
                    raise ValidationError("Event ID is required")
                if Event.objects.filter(id=event_id).exists():
                    event = Event.objects.get(id=event_id)
                    event.title = title
                    event.domain = domain_path
                    event.locale = request.data.get("locale") or "en"
                    event.timezone = request.data.get("timezone") or "UTC"
                    event.trait_grants = trait_grants
                    event.save()
                else:
                    event = Event.objects.create(
                        id=event_id,
                        title=title,
                        domain=domain_path,
                        locale=request.data.get("locale") or "en",
                        timezone=request.data.get("timezone") or "UTC",
                        config=config,
                        trait_grants=trait_grants,
                    )
                configure_video_settings_for_talks.delay(
                    event_id, days=30, number=1, traits=["schedule-update"], long=True
                )
                site_url = settings.SITE_URL
                protocol = get_protocol(site_url)
                event.domain = "{}://{}".format(protocol, domain_path)
                return JsonResponse(model_to_dict(event, exclude=["roles"]), status=201)
            except IntegrityError as e:
                logger.error(f"Database integrity error while saving event: {e}")
                return JsonResponse(
                    {
                        "error": "An event with this ID already exists or database constraint violated"
                    },
                    status=400,
                )
            except ValidationError as e:
                logger.error(f"Validation error while saving event: {e}")
                return JsonResponse({"error": str(e)}, status=400)
            except Exception as e:
                logger.error(f"Unexpected error creating event: {e}")
                return JsonResponse(
                    {"error": "An unexpected error occurred"}, status=500
                )
        else:
            return JsonResponse(
                {"error": "Event cannot be created due to missing permission"},
                status=403,
            )

    @staticmethod
    def get_payload_from_token(request):
        auth_header = get_authorization_header(request).split()
        if auth_header and auth_header[0].lower() == b"bearer":
            if len(auth_header) == 1:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. No credentials provided."
                )
            elif len(auth_header) > 2:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. Token string should not contain spaces."
                )
        try:
            payload = jwt.decode(
                auth_header[1], settings.SECRET_KEY, algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token has expired")
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed("Invalid token")
        return payload


class UserFavouriteView(APIView):
    permission_classes = []

    @staticmethod
    def post(request, *args, **kwargs) -> JsonResponse:
        """
        Handle POST requests to add talks to the user's favourite list.
        Being called by eventyay-talk, authenticate by bearer token.
        """
        try:
            talk_list = json.loads(request.body.decode())
            user_code = UserFavouriteView.get_uid_from_token(
                request, kwargs["event_id"]
            )
            user = User.objects.get(token_id=user_code)
            if not user_code or not user:
                # user not created yet, no error should be returned
                logger.error("User not found for adding favourite talks.")
                return JsonResponse([], safe=False, status=200)
            if user.client_state is None:
                # If it's None, create a new dictionary with schedule.favs field
                user.client_state = {"schedule": {"favs": talk_list}}
            else:
                # If client_state is not None, check if 'schedule' field exists
                if "schedule" not in user.client_state:
                    # If 'schedule' field doesn't exist, create it
                    user.client_state["schedule"] = {"favs": talk_list}
                else:
                    # If 'schedule' field exists, update the 'favs' field
                    user.client_state["schedule"]["favs"] = talk_list
            user.save()
            return JsonResponse(talk_list, safe=False, status=200)
        except Exception as e:
            logger.error(
                "error happened when trying to add fav talks: %s",
                kwargs["event_id"],
            )
            logger.error(e)
            # Since this is called from background so no error should be returned
            return JsonResponse([], safe=False, status=200)

    @staticmethod
    def get_uid_from_token(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        auth_header = get_authorization_header(request).split()
        if auth_header and auth_header[0].lower() == b"bearer":
            if len(auth_header) == 1:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. No credentials provided."
                )
            elif len(auth_header) > 2:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. Token string should not contain spaces."
                )
        token_decode = event.decode_token(token=auth_header[1])
        return token_decode.get("uid")


class ExportView(APIView):
    permission_classes = []

    @staticmethod
    def get(request, *args, **kwargs):
        export_type = request.GET.get("export_type", "json")
        event = get_object_or_404(Event, id=kwargs["event_id"])
        talk_config = event.config.get("pretalx")
        user = User.objects.filter(token_id=request.user)
        talk_base_url = (
            talk_config.get("domain")
            + "/"
            + talk_config.get("event")
            + "/schedule/export/"
        )
        export_endpoint = "schedule." + export_type
        talk_url = talk_base_url + export_endpoint
        if "my" in export_type and user:
            user_state = user.first().client_state
            if (
                user_state
                and user_state.get("schedule")
                and user_state.get("schedule").get("favs")
            ):
                talk_list = user_state.get("schedule").get("favs")
                talk_list_str = ",".join(talk_list)
                export_endpoint = "schedule-my." + export_type.replace("my", "")
                talk_url = talk_base_url + export_endpoint + "?talks=" + talk_list_str
        header = {"Content-Type": "application/json"}
        response = requests.get(talk_url, headers=header)
        return Response(response.content.decode("utf-8"))


def get_domain(path):
    if not path:
        return ""
    domain = urlparse(path).netloc
    if ":" in domain:
        domain = domain.split(":")[0]
    return domain.lower()


@api_view(http_method_names=["POST"])
@permission_classes([ApiAccessRequiredPermission])
def schedule_update(request, **kwargs):
    """POST endpoint to notify eventyay that schedule data has changed.

    Optionally, the request may contain data for the ``pretalx`` field in the
    event config.
    """
    domain = get_domain(request.data.get("domain"))
    event = request.data.get("event")

    if not domain or not event:
        return Response("Missing fields in request.", status=401)

    pretalx_config = request.event.config.get("pretalx", {})
    if domain != get_domain(
        pretalx_config.get("domain")
    ) or event != pretalx_config.get("event"):
        return Response("Incorrect domain or event data", status=401)

    # We assume that only pretalx uses this endpoint
    request.event.config["pretalx"]["connected"] = True
    request.event.config["pretalx"]["pushed"] = now().isoformat()
    request.event.save()

    async_to_sync(notify_schedule_change)(request.event.id)
    return Response(status=200)


@api_view(http_method_names=["POST"])
@permission_classes([UserDeletePermissions])
def delete_user(request, **kwargs):
    """POST endpoint to soft-delete a user.

    This endpoint is called with a single POST parameter, 'user_id'."""
    user_id = request.data.get("user_id")
    token_id = request.data.get("token_id")
    if not user_id and not token_id:
        return Response("Missing user ID.", status=400)
    if user_id and token_id:
        return Response("Ambiguous user ID.", status=400)

    user = None
    with suppress(exceptions.ValidationError):  # raised when user_id isn't a uid
        if user_id:
            user = User.objects.filter(id=user_id, deleted=False).first()
        elif token_id:
            user = User.objects.filter(token_id=token_id, deleted=False).first()
    if not user:
        return Response(status=404)

    user.soft_delete()
    return Response(status=204)
