from rest_framework.permissions import SAFE_METHODS, BasePermission


class ApiPermission(BasePermission):

    def get_permission_object(self, view, obj, request, detail=False):
        if func := getattr(view, "get_permission_object", None):
            return func()
        return obj or request.event

    def has_permission(self, request, view):
        return self._has_permission(view, None, request)

    def has_object_permission(self, request, view, obj):
        return self._has_permission(view, obj, request)

    def _has_permission(self, view, obj, request):
        event = getattr(request, "event", None)
        if not event:  # Only true for root API view
            return True

        permission_object = self.get_permission_object(
            view, obj, request, detail=view.detail
        )
        if permission_map := getattr(view, "permission_map", None):
            suffix = "_object" if obj else ""
            if permission_required := permission_map.get(f"{view.action}{suffix}"):
                return request.user.has_perm(permission_required, permission_object)

        if request.method in SAFE_METHODS:
            read_permission = getattr(view, "read_permission_required", None)
            if read_permission:
                return request.user.has_perm(read_permission, permission_object)
            return True

        write_permission = getattr(view, "write_permission_required", None)
        if write_permission:
            return request.user.has_perm(write_permission, permission_object)
        return False


class PluginPermission(ApiPermission):
    """Use this class to restrict access to views based on active plugins.

    Set PluginPermission.plugin_required to the name of the plugin that is required to access the endpoint.
    """

    def has_permission(self, request, view):
        return self._has_permission(view, request)

    def has_object_permission(self, request, view, obj):
        return self._has_permission(view, request)

    def _has_permission(self, view, request):
        event = getattr(request, "event", None)
        if not event:
            # Only events can have plugins
            return False
        plugin_name = getattr(view, "plugin_required", None)
        if not plugin_name:
            return True
        return plugin_name in event.plugin_list
