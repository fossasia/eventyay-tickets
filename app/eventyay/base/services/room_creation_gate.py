from collections import Counter

from eventyay.base.settings import (
    get_provider_for_module_type,
    is_video_provider_enabled_for_organizer,
)
from eventyay.core.permissions import Permission


# TODO(server-room-dev-gate): Remove this gate when server-backed room creation is released to normal roles.
SERVER_BACKED_ROOM_CREATE_PERMISSIONS = {
    "call.bigbluebutton": Permission.EVENT_ROOMS_CREATE_BBB,
    "call.janus": Permission.EVENT_ROOMS_CREATE_BBB,
    "call.jitsi": Permission.EVENT_ROOMS_CREATE_JITSI,
    "call.zoom": Permission.EVENT_ROOMS_CREATE_BBB,
    "networking.roulette": Permission.EVENT_ROOMS_CREATE_BBB,
}
SERVER_BACKED_ROOM_MODULE_TYPES = frozenset(SERVER_BACKED_ROOM_CREATE_PERMISSIONS)


def module_config_contains_server_backed_room(module_config):
    return any(
        isinstance(module, dict)
        and module.get("type") in SERVER_BACKED_ROOM_MODULE_TYPES
        for module in module_config or []
    )


def _server_backed_module_types(module_config):
    return [
        module.get("type")
        for module in module_config or []
        if isinstance(module, dict) and module.get("type") in SERVER_BACKED_ROOM_MODULE_TYPES
    ]


def newly_added_server_backed_room_modules(old_module_config, new_module_config):
    """Return server-backed modules that increase the count of a given type.

    Compares multiplicities so adding a second ``call.bigbluebutton`` (or any
    other server-backed type) is treated as newly added even when that type
    already existed once in the room.
    """
    old_counts = Counter(_server_backed_module_types(old_module_config))
    seen_counts = Counter()
    newly_added = []
    for module in new_module_config or []:
        if not isinstance(module, dict):
            continue
        module_type = module.get("type")
        if module_type not in SERVER_BACKED_ROOM_MODULE_TYPES:
            continue
        seen_counts[module_type] += 1
        if seen_counts[module_type] > old_counts[module_type]:
            newly_added.append(module)
    return newly_added


def has_server_room_development_admin_trait(traits):
    # TODO(server-room-dev-gate): Remove when server-backed room creation is released to normal roles.
    return "admin" in (traits or [])


async def user_can_create_server_backed_room_during_development(user):
    # TODO(server-room-dev-gate): Remove when server-backed room creation is released to normal roles.
    return has_server_room_development_admin_trait(getattr(user, "traits", None))


def server_backed_room_create_permissions(module_config):
    permissions = {
        SERVER_BACKED_ROOM_CREATE_PERMISSIONS[module.get("type")]
        for module in module_config or []
        if isinstance(module, dict)
        and module.get("type") in SERVER_BACKED_ROOM_CREATE_PERMISSIONS
    }
    return sorted(permissions, key=lambda permission: permission.value)


def has_all_server_backed_room_create_permissions(event, *, traits, module_config):
    """Require every distinct create permission for the given modules (AND).

    ``Event.has_permission_implicit`` treats a permission list as OR, so callers
    that need each server-backed type authorized must check permissions one by one.
    """
    permissions = server_backed_room_create_permissions(module_config)
    if not permissions:
        return False
    return all(
        event.has_permission_implicit(traits=traits, permissions=[permission])
        for permission in permissions
    )


async def user_has_all_server_backed_room_create_permissions(event, user, module_config):
    permissions = server_backed_room_create_permissions(module_config)
    if not permissions:
        return False
    for permission in permissions:
        if not await event.has_permission_async(user=user, permission=permission):
            return False
    return True


def is_module_type_enabled_for_creation(module_type: str) -> bool:
    provider = get_provider_for_module_type(module_type)
    if provider:
        return is_video_provider_enabled_for_organizer(provider)
    return True


def is_module_config_enabled_for_creation(module_config) -> bool:
    for module in module_config or []:
        if isinstance(module, dict):
            module_type = module.get("type")
            if not is_module_type_enabled_for_creation(module_type):
                return False
    return True


def newly_added_provider_modules(old_module_config, new_module_config):
    old_counts = Counter(
        module.get("type")
        for module in old_module_config or []
        if isinstance(module, dict) and get_provider_for_module_type(module.get("type"))
    )
    seen_counts = Counter()
    newly_added = []
    for module in new_module_config or []:
        if not isinstance(module, dict):
            continue
        module_type = module.get("type")
        if not get_provider_for_module_type(module_type):
            continue
        seen_counts[module_type] += 1
        if seen_counts[module_type] > old_counts[module_type]:
            newly_added.append(module)
    return newly_added


