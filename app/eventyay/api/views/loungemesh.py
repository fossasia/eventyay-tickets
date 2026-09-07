import json
import logging
from datetime import timedelta

from django.http import JsonResponse
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from eventyay.base.services.loungemesh import (
    DEFAULT_FEATURES,
    get_loungemesh_server,
    issue_jitsi_jwt,
    loungemesh_is_available,
    verify_loungemesh_token,
    verify_server_api_secret,
)
from eventyay.base.settings import is_video_provider_enabled_for_attendee

logger = logging.getLogger(__name__)


def extract_api_secret(request, body: dict) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    if auth_header.startswith("Token "):
        return auth_header[6:].strip()

    for header in ("X-LoungeMesh-Secret", "X-Api-Secret", "X-LoungeMesh-Key"):
        val = request.headers.get(header)
        if val:
            return val.strip()

    if isinstance(body, dict) and "api_secret" in body:
        return str(body.get("api_secret", "")).strip()
    return None


@method_decorator(csrf_exempt, name="dispatch")
class LoungeMeshTokenExchangeView(View):
    def post(self, request, *args, **kwargs):
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid_json"}, status=400)

        token_str = body.get("token", "").strip()
        if not token_str:
            return JsonResponse({"error": "token_required"}, status=400)

        token_obj = verify_loungemesh_token(token_str)
        if not token_obj:
            return JsonResponse({"error": "invalid_or_expired_token"}, status=403)

        event = token_obj.event
        if not is_video_provider_enabled_for_attendee("loungemesh") or not loungemesh_is_available(event):
            return JsonResponse(
                {"error": "feature_disabled", "message": "LoungeMesh is currently disabled by administrator."},
                status=403,
            )

        server = get_loungemesh_server(event)
        secret_candidate = extract_api_secret(request, body)
        if server and server.api_secret:
            if not verify_server_api_secret(server, secret_candidate):
                logger.warning("LoungeMesh token exchange unauthorized: missing or invalid API secret.")
                return JsonResponse(
                    {"error": "unauthorized", "message": "Invalid or missing LoungeMesh API secret."},
                    status=401,
                )

        room = token_obj.room
        user = token_obj.user

        # Extract features from room config
        room_features = dict(DEFAULT_FEATURES)
        for mod in (room.module_config or []):
            if isinstance(mod, dict) and mod.get("type") in ("call.loungemesh", "channel.loungemesh"):
                room_features.update(mod.get("config", {}).get("features", {}))

        display_name = "Attendee"
        avatar = ""
        if user:
            display_name = getattr(user, "name", "") or getattr(user, "fullname", "")
            if not display_name and hasattr(user, "profile") and isinstance(user.profile, dict):
                display_name = user.profile.get("display_name", "")
            if hasattr(user, "profile") and isinstance(user.profile, dict):
                avatar = user.profile.get("avatar_url", "")
            if not display_name:
                display_name = str(getattr(user, "email", "Attendee")).split("@")[0]

        jitsi_room = f"lms-{event.slug}-{room.pk}"
        server = get_loungemesh_server(event)
        jitsi_jwt = None
        if server and server.jitsi_app_secret:
            jitsi_jwt = issue_jitsi_jwt(
                display_name=display_name,
                jitsi_room=jitsi_room,
                moderator=token_obj.moderator,
                features=room_features,
                app_id=server.jitsi_app_id,
                app_secret=server.jitsi_app_secret,
                avatar=avatar,
            )

        return JsonResponse(
            {
                "status": "granted",
                "jwt": jitsi_jwt,
                "display_name": display_name,
                "avatar": avatar,
                "jitsi_room": jitsi_room,
                "moderator": bool(token_obj.moderator),
                "features": room_features,
                "expires_at": token_obj.expires.isoformat(),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class LoungeMeshTokenRefreshView(View):
    def post(self, request, *args, **kwargs):
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid_json"}, status=400)

        token_str = body.get("token", "").strip()
        if not token_str:
            return JsonResponse({"error": "token_required"}, status=400)

        token_obj = verify_loungemesh_token(token_str)
        if not token_obj:
            return JsonResponse({"error": "invalid_or_expired_token"}, status=403)

        # Extend expiry
        token_obj.expires = now() + timedelta(hours=2)
        token_obj.save(update_fields=["expires"])

        event = token_obj.event
        if not is_video_provider_enabled_for_attendee("loungemesh") or not loungemesh_is_available(event):
            return JsonResponse(
                {"error": "feature_disabled", "message": "LoungeMesh is currently disabled by administrator."},
                status=403,
            )

        server = get_loungemesh_server(event)
        secret_candidate = extract_api_secret(request, body)
        if server and server.api_secret:
            if not verify_server_api_secret(server, secret_candidate):
                logger.warning("LoungeMesh token refresh unauthorized: missing or invalid API secret.")
                return JsonResponse(
                    {"error": "unauthorized", "message": "Invalid or missing LoungeMesh API secret."},
                    status=401,
                )

        room = token_obj.room
        user = token_obj.user

        display_name = "Attendee"
        avatar = ""
        if user:
            display_name = getattr(user, "name", "") or getattr(user, "fullname", "")
            if not display_name and hasattr(user, "profile") and isinstance(user.profile, dict):
                display_name = user.profile.get("display_name", "")
            if hasattr(user, "profile") and isinstance(user.profile, dict):
                avatar = user.profile.get("avatar_url", "")

        jitsi_room = f"lms-{event.slug}-{room.pk}"
        server = get_loungemesh_server(event)
        jitsi_jwt = None
        if server and server.jitsi_app_secret:
            jitsi_jwt = issue_jitsi_jwt(
                display_name=display_name,
                jitsi_room=jitsi_room,
                moderator=token_obj.moderator,
                app_id=server.jitsi_app_id,
                app_secret=server.jitsi_app_secret,
                avatar=avatar,
            )

        return JsonResponse(
            {
                "status": "refreshed",
                "jwt": jitsi_jwt,
                "display_name": display_name,
                "jitsi_room": jitsi_room,
                "moderator": bool(token_obj.moderator),
                "expires_at": token_obj.expires.isoformat(),
            }
        )
