from rest_framework.permissions import SAFE_METHODS, BasePermission


class ApiPermission(BasePermission):
    def _has_permission(self, view, obj, request):
        event = getattr(request, "event", None)
        if not event:  # Only true for root API view
            return True

        if request.method in SAFE_METHODS:
            read_permission = getattr(view, "read_permission_required", None)
            if read_permission:
                return request.user.has_perm(read_permission, obj)
            return True

        write_permission = getattr(view, "write_permission_required", None)
        if write_permission:
            return request.user.has_perm(write_permission, obj)
        return False

    def has_permission(self, request, view):
        return self._has_permission(view, getattr(request, "event", None), request)

    def has_object_permission(self, request, view, obj):
        return self._has_permission(view, obj, request)
