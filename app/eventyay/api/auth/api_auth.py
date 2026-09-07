from django.shortcuts import get_object_or_404
from rest_framework import authentication, exceptions, permissions
from rest_framework.authentication import get_authorization_header

from eventyay.base.models.event import Event
from eventyay.base.models.room import Room
from eventyay.base.services.room_creation_gate import (
    has_all_server_backed_room_create_permissions,
    has_server_room_development_admin_trait,
    is_module_config_enabled_for_creation,
    module_config_contains_server_backed_room,
    newly_added_provider_modules,
    newly_added_server_backed_room_modules,
)
from eventyay.base.settings import get_provider_for_module_type, is_video_provider_enabled_for_organizer
from eventyay.core.permissions import Permission


class EventTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    """
    Authentification works like the frontend, but since the REST API currently does not allow any operations for
    which the logged-in user is relevant, we do not persist the user to the database but only keep the traits
    in the current request.
    """

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            msg = "Invalid token header. No credentials provided."
            raise exceptions.NotAuthenticated(msg)
        elif len(auth) > 2:
            msg = "Invalid token header. Token string should not contain spaces."
            raise exceptions.AuthenticationFailed(msg)

        try:
            token = auth[1].decode()
        except UnicodeError:
            msg = "Invalid token header. Token string should not contain invalid characters."
            raise exceptions.AuthenticationFailed(msg)

        event_id = request.resolver_match.kwargs["event_id"]
        request.event = get_object_or_404(Event, id=event_id)
        return self.authenticate_credentials(token, request.event)

    def authenticate_credentials(self, key, event):
        try:
            token = event.decode_token(key)
            if not token:
                raise exceptions.AuthenticationFailed("Invalid token.")
        except Exception:
            raise exceptions.AuthenticationFailed("Invalid token.")

        return token.get("uid"), token


class NoPermission(permissions.BasePermission):
    def has_permission(self, request, view):  # pragma: no cover
        return False


class ApiAccessRequiredPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if isinstance(request.user, AnonymousUser):
            return False
        return request.event.has_permission_implicit(
            traits=request.auth.get("traits"),
            permissions=[Permission.EVENT_API],
        )


class EventPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        traits = request.auth.get("traits")
        if not request.event.has_permission_implicit(
            traits=traits, permissions=[Permission.EVENT_SECRETS]
        ):
            return False
        if request.method in ("PATCH", "PUT", "POST"):
            return request.event.has_permission_implicit(
                traits=traits, permissions=[Permission.EVENT_UPDATE]
            )
        elif request.method in ("HEAD", "GET", "OPTIONS"):
            return True
        return False


class UserDeletePermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        traits = request.auth.get("traits")
        return request.event.has_permission_implicit(
            traits=traits,
            permissions=[Permission.EVENT_USERS_MANAGE],
        )


class RoomPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            traits = request.auth.get("traits")
            module_config = request.data.get("module_config")
            if not is_module_config_enabled_for_creation(module_config):
                return False
            # Server-backed modules need the development admin gate in addition to
            # the usual create-permission check (do not return early — mixed
            # payloads still need the general room-create permission check).
            if module_config_contains_server_backed_room(module_config):
                if not (
                    has_server_room_development_admin_trait(traits)
                    and has_all_server_backed_room_create_permissions(
                        request.event,
                        traits=traits,
                        module_config=module_config,
                    )
                ):
                    return False
            return request.event.has_permission_implicit(
                traits=traits,
                permissions=[
                    Permission.EVENT_ROOMS_CREATE_STAGE,
                    Permission.EVENT_ROOMS_CREATE_BBB,
                    Permission.EVENT_ROOMS_CREATE_JITSI,
                    Permission.EVENT_ROOMS_CREATE_CHAT,
                ],
            )
        else:
            return True

    def has_object_permission(self, request, view, obj: Room):
        permission = None
        traits = request.auth.get("traits")
        module_config = request.data.get("module_config")
        newly_added_server_modules = newly_added_server_backed_room_modules(
            obj.module_config,
            module_config,
        )
        if request.method in ("PATCH", "PUT") and newly_added_server_modules:
            if not (
                has_server_room_development_admin_trait(traits)
                and has_all_server_backed_room_create_permissions(
                    request.event,
                    traits=traits,
                    module_config=newly_added_server_modules,
                )
            ):
                return False
        newly_added_providers = newly_added_provider_modules(
            obj.module_config,
            module_config,
        )
        if request.method in ("PATCH", "PUT") and newly_added_providers:
            for module in newly_added_providers:
                provider = get_provider_for_module_type(module.get("type"))
                if provider and not is_video_provider_enabled_for_organizer(provider):
                    return False
        if request.method in ("PATCH", "PUT"):
            permission = Permission.ROOM_UPDATE
        elif request.method == "DELETE":
            permission = Permission.ROOM_DELETE
        if permission:
            return request.event.has_permission_implicit(
                permissions=[permission], traits=traits
            )
        else:
            return True


class AnonymousUser:
    pass
