import rules
from django.db.models import Q


@rules.predicate
def is_event_visible(user, event):
    return event and event.is_public


def get_events_for_user(user, queryset=None):
    from pretalx.event.models import Event

    queryset = queryset or Event.objects.all()
    if user.is_anonymous:
        queryset = queryset.filter(is_public=True)
    else:
        events = user.get_events_with_any_permission().values_list("pk", flat=True)
        queryset = queryset.filter(Q(is_public=True) | Q(pk__in=events))
    return queryset.order_by("-date_from")


def check_team_permission(user, event, permission):
    # We could query for a matching team here, which would be more efficient
    # if we only ever wanted to know this. But realistically, there will be
    # more permission checks regarding the event permissions a user has,
    # and get_permissions_for_event is cached, so it is overall more efficient.
    return user.is_administrator or permission in user.get_permissions_for_event(event)


@rules.predicate
def can_change_event_settings(user, obj):
    event = getattr(obj, "event", None)
    if not event or not obj or not user or user.is_anonymous:
        return False
    return check_team_permission(user, event, "can_change_event_settings")


@rules.predicate
def can_change_teams(user, obj):
    if not user or user.is_anonymous:
        return False
    if user.is_administrator:
        return True
    if event := getattr(obj, "event", None):
        return check_team_permission(user, event, "can_change_teams")
    return user.teams.filter(organiser=obj.organiser, can_change_teams=True).exists()


@rules.predicate
def can_change_organiser_settings(user, obj):
    event = getattr(obj, "event", None)
    if event:
        obj = event.organiser
    return (
        user.is_administrator
        or user.teams.filter(organiser=obj, can_change_organiser_settings=True).exists()
    )


@rules.predicate
def has_any_permission(user, obj):
    return bool(user.get_permissions_for_event(obj.event))


@rules.predicate
def has_any_organiser_permissions(user, obj):
    organiser = getattr(obj, "organiser", None) or obj
    return user.is_administrator or user.teams.filter(organiser=organiser).exists()


@rules.predicate
def can_change_any_organiser_settings(user, obj):
    return (
        user.is_administrator
        or user.teams.filter(can_change_organiser_settings=True).exists()
    )


@rules.predicate
def can_create_events(user, obj):
    return user.is_administrator or user.teams.filter(can_create_events=True).exists()


@rules.predicate
def is_any_organiser(user, obj):
    return user.is_administrator or user.teams.all().exists()