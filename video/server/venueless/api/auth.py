from django.shortcuts import get_object_or_404
from rest_framework import authentication, exceptions, permissions
from rest_framework.authentication import get_authorization_header

from venueless.core.models import Room, World
from venueless.core.services.world import has_permission


class WorldTokenAuthentication(authentication.BaseAuthentication):
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

        world_id = request.resolver_match.kwargs["world_id"]
        request.world = get_object_or_404(World, id=world_id)
        return self.authenticate_credentials(token, request.world)

    def authenticate_credentials(self, key, world):
        try:
            token = world.decode_token(key)
            if not token:
                raise exceptions.AuthenticationFailed("Invalid token.")
        except:
            raise exceptions.AuthenticationFailed("Invalid token.")

        return token.get("uid"), token


class NoPermission(permissions.BasePermission):
    def has_permission(self, request, view):  # pragma: no cover
        return False


class ApiAccessRequiredPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if isinstance(request.user, AnonymousUser):
            return False
        permset = request.world.permission_config
        perm_key = "world.api"
        return perm_key in permset and has_permission(
            permset[perm_key], request.auth.get("traits")
        )


class WorldPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        permset = request.world.permission_config
        if not has_permission(permset["world.secrets"], request.auth.get("traits")):
            return False
        if request.method in ("PATCH", "PUT"):
            perm_key = "world.update"
            return perm_key in permset and has_permission(
                permset[perm_key], request.auth.get("traits")
            )
        elif request.method in ("HEAD", "GET", "OPTIONS"):
            return True
        return False


class RoomPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            permset = request.world.permission_config
            perm_key = "room.create"
            return perm_key in permset and has_permission(
                permset[perm_key], request.auth.get("traits")
            )
        else:
            return True

    def has_object_permission(self, request, view, obj: Room):
        permset = request.world.permission_config
        permset.update(obj.permission_config)

        perm_key = None
        if request.method in ("PATCH", "PUT"):
            perm_key = "room.update"
        elif request.method == "DELETE":
            perm_key = "room.delete"
        if perm_key:
            return perm_key in permset and has_permission(
                permset[perm_key], request.auth.get("traits")
            )
        else:
            return True


class AnonymousUser:
    pass
