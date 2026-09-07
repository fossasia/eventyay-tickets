import random
from django.db.models import Q


def filter_servers_for_event(queryset, event):
    """
    Returns querysets partitioned by priority for an event:
    1. event_exclusive_qs: explicit matches on event (via `events` ManyToMany or legacy `event_exclusive`)
    2. organizer_exclusive_qs: matches on the event's organizer (via `organizers` ManyToMany)
    3. global_qs: servers with no restrictions (no events, no organizers, no event_exclusive)

    Yields or returns a list of candidate querysets in precedence order.
    """
    search_order = []

    if event:
        # Tier 1: Event-specific servers
        event_qs = queryset.filter(
            Q(events=event) | Q(event_exclusive=event)
        ).distinct()
        search_order.append(event_qs)

        # Tier 2: Organizer-scoped servers
        organizer = getattr(event, "organizer", None)
        if organizer:
            organizer_qs = queryset.filter(organizers=organizer).distinct()
            search_order.append(organizer_qs)

    # Tier 3: Global unscoped servers (available to all events and organizers)
    global_qs = queryset.filter(
        events__isnull=True,
        organizers__isnull=True,
        event_exclusive__isnull=True,
    ).distinct()
    search_order.append(global_qs)

    return search_order


def is_server_available_for_event(server, event) -> bool:
    """
    Checks whether a specific server instance is authorized for an event.
    A server is authorized if:
    - It is explicitly assigned to the event (via events or event_exclusive)
    - It is assigned to the event's organizer (via organizers)
    - It is global (no events, organizers, or event_exclusive assigned)
    """
    if not event:
        return True

    has_events = server.events.exists()
    has_organizers = server.organizers.exists()
    has_exclusive = bool(server.event_exclusive_id)

    # If unconstrained, it's global
    if not has_events and not has_organizers and not has_exclusive:
        return True

    if has_exclusive and server.event_exclusive_id == event.id:
        return True

    if has_events and server.events.filter(pk=event.pk).exists():
        return True

    organizer = getattr(event, "organizer", None)
    if organizer and has_organizers and server.organizers.filter(pk=organizer.pk).exists():
        return True

    return False
