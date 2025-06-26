from rest_framework.permissions import BasePermission

from pretalx.person.rules import is_only_reviewer

MODEL_PERMISSION_MAP = {
    "list": "list",
    "retrieve": "view",
    "update": "update",
    "partial_update": "update",
    "destroy": "delete",
}

MODEL_PERMISSION_MAP = {
    "list": "list",
    "retrieve": "view",
    "update": "update",
    "partial_update": "update",
    "destroy": "delete",
}


class ApiPermission(BasePermission):

    def get_permission_object(self, view, obj, request, detail=False):
        return obj or getattr(request, "event", None) or request.organiser

    def has_permission(self, request, view):
        return self._has_permission(view, None, request)

    def has_object_permission(self, request, view, obj):
        return self._has_permission(view, obj, request)

    def _has_permission(self, view, obj, request):
        """
        We check multiple levels of permissions:
        - Is the auth token active in the first place (not expired)
        - Does the auth token have access to the event
        - Does the auth token have access to the endpoint (with the method used)
        - Does the user have the required additional object-level permissions
        """
        event = getattr(request, "event", None)
        if request.auth:
            if event:
                if event not in request.auth.events.all():
                    return False
                if is_only_reviewer(request.user, request.event):
                    # Reviewers can only access the API if there is an active review
                    # phase AND no anonymisation is active, as otherwise, we can’t fully
                    # guarantee that we’d accidentally expose speaker names or other
                    # non-anonymised information through ?expand= lookups.
                    if (
                        not event.active_review_phase
                        or not event.active_review_phase.can_see_speaker_names
                    ):
                        return False
            endpoint = getattr(view, "endpoint", None)
            if not request.auth.has_endpoint_permission(endpoint, view.action):
                return False

        if view.detail and not obj:
            # Early out as DRF will check permissions on detail endpoints twice,
            # once without an object passed and once with.
            return True

        permission_object = self.get_permission_object(
            view, obj, request, detail=view.detail
        )
        permission_map = getattr(view, "permission_map", None) or {}
        permission_required = permission_map.get(view.action)
        if not permission_required:
            model_action = MODEL_PERMISSION_MAP.get(view.action, view.action)
            permission_required = view.queryset.model.get_perm(model_action)
        return request.user.has_perm(permission_required, permission_object)


class PluginPermission(ApiPermission):  # pragma: no cover
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
