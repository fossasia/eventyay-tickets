import logging
import secrets
from datetime import timedelta
import time
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Q
from django.utils.timezone import now
import jwt

from eventyay.base.models import LoungeMeshAccessToken, LoungeMeshServer, Room
from .video_server_routing import filter_servers_for_event, is_server_available_for_event

logger = logging.getLogger(__name__)

DEFAULT_FEATURES = {
    "notes": True,
    "whiteboard": True,
    "spatial_chat": True,
}


def normalize_server_url(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def get_loungemesh_server(event=None, prefer_server=None) -> LoungeMeshServer | None:
    servers = LoungeMeshServer.objects.filter(active=True)
    if not servers.exists():
        return None

    if prefer_server:
        preferred = normalize_server_url(prefer_server)
        for s in servers:
            if normalize_server_url(s.url) == preferred and is_server_available_for_event(s, event):
                return s

    search_order = filter_servers_for_event(servers, event)
    for qs in search_order:
        s = qs.first()
        if s:
            return s

    return servers.first()


def loungemesh_is_available(event=None) -> bool:
    return LoungeMeshServer.objects.filter(active=True).exists()


def issue_opaque_token(
    event, room, user, moderator: bool = False, expires_in_seconds: int = 7200
) -> LoungeMeshAccessToken:
    auth_user = user if user and getattr(user, "is_authenticated", False) else None
    return LoungeMeshAccessToken.objects.create(
        event=event,
        room=room,
        user=auth_user,
        moderator=moderator,
        expires=now() + timedelta(seconds=expires_in_seconds),
    )


def verify_loungemesh_token(token_str: str) -> LoungeMeshAccessToken | None:
    if not token_str:
        return None
    token = LoungeMeshAccessToken.objects.filter(
        token=token_str,
        expires__gt=now(),
    ).select_related("event", "room", "user").first()
    return token


def verify_server_api_secret(server: LoungeMeshServer | None, secret_candidate: str | None) -> bool:
    """Verify an API secret provided by the LoungeMesh server using constant-time comparison."""
    if not server or not server.api_secret:
        return True
    if not secret_candidate:
        return False
    return secrets.compare_digest(server.api_secret.strip(), secret_candidate.strip())


def issue_jitsi_jwt(
    display_name: str,
    jitsi_room: str,
    moderator: bool = False,
    features: dict | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
    avatar: str | None = None,
) -> str | None:
    if not app_secret:
        return None

    now_ts = int(time.time())
    payload = {
        "context": {
            "user": {
                "name": display_name,
                "avatar": avatar or "",
                "moderator": moderator,
            },
            "features": features or DEFAULT_FEATURES,
        },
        "aud": app_id or "loungemesh",
        "iss": app_id or "loungemesh",
        "sub": app_id or "*",
        "room": jitsi_room,
        "iat": now_ts,
        "nbf": now_ts - 10,
        "exp": now_ts + 7200,
    }
    return jwt.encode(payload, app_secret, algorithm="HS256")


def issue_join_url(
    event, room, user, moderator: bool = False, server: LoungeMeshServer | None = None
) -> str | None:
    server_obj = server or get_loungemesh_server(event)
    if not server_obj:
        return None

    # Room must have loungemesh in module_config
    has_loungemesh = any(
        isinstance(m, dict) and m.get("type") in ("call.loungemesh", "channel.loungemesh")
        for m in (room.module_config or [])
    )
    if not has_loungemesh:
        return None

    token = issue_opaque_token(event, room, user, moderator=moderator)
    base_url = server_obj.url.rstrip("/")
    jitsi_room = f"lms-{event.slug}-{room.pk}"
    return f"{base_url}/join/{jitsi_room}?token={token.token}&event={event.slug}&room={room.pk}"


def clean_expired_loungemesh_tokens(sender=None):
    deleted_count, _ = LoungeMeshAccessToken.objects.filter(expires__lt=now()).delete()
    return deleted_count


def loungemesh_embed_origins() -> list[str]:
    origins = set()
    for s in LoungeMeshServer.objects.filter(active=True):
        origin = normalize_server_url(s.url)
        if origin:
            origins.add(origin)
    # Default fallbacks
    origins.add("http://localhost:8780")
    origins.add("https://loungemesh.com")
    return sorted(list(origins))


def loungemesh_permissions_policy(extra_origins=None) -> str:
    origins = set(loungemesh_embed_origins())
    if extra_origins:
        origins.update(extra_origins)
    formatted_origins = " ".join(f'"{o}"' for o in sorted(origins))
    return (
        f"camera=(self {formatted_origins}), "
        f"microphone=(self {formatted_origins}), "
        f"display-capture=(self {formatted_origins}), "
        f"clipboard-read=(self {formatted_origins}), "
        f"clipboard-write=(self {formatted_origins})"
    )


def apply_loungemesh_embed_headers(response, extra_origins=None):
    response["Permissions-Policy"] = loungemesh_permissions_policy(extra_origins)
    origins = list(loungemesh_embed_origins())
    if extra_origins:
        origins.extend(extra_origins)
    if not hasattr(response, "_csp_update"):
        response._csp_update = {}
    response._csp_update.setdefault("frame-src", []).extend(origins)
