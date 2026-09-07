import random
from urllib.parse import urlparse

from django.db import transaction
from django.db.models import Q

from eventyay.base.models import JitsiServer, Room
from .video_server_routing import filter_servers_for_event, is_server_available_for_event


class JitsiServerUnavailable(Exception):
    pass


def module_config_contains_jitsi(module_config):
    return any(
        isinstance(module, dict) and module.get("type") == "call.jitsi"
        for module in module_config or []
    )


def has_jitsi_development_admin_trait(traits):
    # TODO(jitsi-dev-gate): Remove when Jitsi room creation is released to normal roles.
    return "admin" in (traits or [])


async def user_can_create_jitsi_room_during_development(user):
    # TODO(jitsi-dev-gate): Remove when Jitsi room creation is released to normal roles.
    if getattr(user, "is_administrator", False):
        return True
    if has_jitsi_development_admin_trait(getattr(user, "traits", None)):
        return True
    get_role_grants_async = getattr(user, "get_role_grants_async", None)
    if get_role_grants_async is None:
        return False
    return "admin" in await get_role_grants_async()


def choose_server(event, prefer_server=None):
    servers = JitsiServer.objects.filter(active=True)
    if prefer_server:
        preferred_server = _choose_preferred_server(servers, event, prefer_server)
        if preferred_server:
            return preferred_server
    return _choose_any_available_server(servers, event)


def _choose_preferred_server(servers, event, prefer_server):
    preferred = normalize_server_url(prefer_server)
    if not preferred:
        return None
    preferred_servers = [
        server
        for server in servers
        if _server_matches_preference(server, preferred) and is_server_available_for_event(server, event)
    ]
    if preferred_servers:
        return random.choice(preferred_servers)
    return None


def _choose_any_available_server(servers, event):
    querysets = filter_servers_for_event(servers, event)
    for qs in querysets:
        available_servers = list(qs)
        if available_servers:
            self_hosted = [
                s for s in available_servers if "meet.jit.si" not in (s.url or "")
            ]
            if self_hosted:
                return random.choice(self_hosted)
            return random.choice(available_servers)
    return None



@transaction.atomic
def choose_server_for_room(room, prefer_server=None):
    locked_room = Room.objects.select_for_update().select_related("event").get(pk=room.pk)
    jitsi_config = _get_jitsi_config(locked_room)
    if jitsi_config is None:
        return choose_server(event=locked_room.event, prefer_server=prefer_server)
    selected_server_url = jitsi_config.get("selected_server_url")
    servers = JitsiServer.objects.filter(active=True)
    server = None
    for preferred_url in (selected_server_url, prefer_server):
        if not preferred_url:
            continue
        # Avoid routing to meet.jit.si when self-hosted servers exist to prevent external authentication barrier
        if "meet.jit.si" in preferred_url and servers.exclude(url__icontains="meet.jit.si").exists():
            continue
        server = _choose_preferred_server(servers, locked_room.event, preferred_url)
        if server:
            break
    if server is None:
        server = _choose_any_available_server(servers, locked_room.event)
    if server is None:
        return None

    normalized = normalize_server_url(server.url)
    if normalized and selected_server_url != normalized["url"]:
        jitsi_config["selected_server_url"] = normalized["url"]
        locked_room.save(update_fields=["module_config"])
    return server


def _get_jitsi_config(room):
    for module in room.module_config or []:
        if not isinstance(module, dict):
            continue
        if module.get("type") == "call.jitsi":
            config = module.setdefault("config", {})
            if not isinstance(config, dict):
                config = {}
                module["config"] = config
            return config
    return None


def _server_matches_preference(server, preferred):
    normalized = normalize_server_url(server.url)
    return bool(
        normalized
        and (
            normalized["url"] == preferred["url"]
            or normalized["domain"] == preferred["domain"]
        )
    )


def choose_server_or_raise(event, prefer_server=None):
    server = choose_server(event=event, prefer_server=prefer_server)
    if server is None:
        raise JitsiServerUnavailable(
            f"No active Jitsi server available for event {event.pk}."
        )
    return server


def normalize_server_url(url):
    if not url:
        return None
    url = url.strip()
    if "://" not in url:
        normalized = url.strip("/").lower()
        return {
            "domain": normalized,
            "url": f"https://{normalized}",
            "protocol": "https:",
        }
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    domain = parsed.netloc.lower()
    scheme = parsed.scheme.lower()
    if scheme not in ("https", "http"):
        return None
    protocol = f"{scheme}:"
    return {
        "domain": domain,
        "url": f"{scheme}://{domain}",
        "protocol": protocol,
    }
