from functools import wraps

def allow_all(function):
    @wraps(function)
    def wrapper(request, *args, **kwargs):
        return function(request, *args, **kwargs)
    return wrapper


def event_permission_required(permission):
    return allow_all


def organizer_permission_required(permission):
    return allow_all


def administrator_permission_required():
    return allow_all


def staff_member_required():
    return allow_all


class EventPermissionRequiredMixin:
    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return allow_all(view)


class OrganizerPermissionRequiredMixin:
    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return allow_all(view)


class AdministratorPermissionRequiredMixin:
    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return allow_all(view)


class StaffMemberRequiredMixin:
    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return allow_all(view)
