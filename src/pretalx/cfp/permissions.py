import rules

from pretalx.person.permissions import is_orga


@rules.predicate
def is_event_visible(user, event):
    return event and event.is_public


rules.add_perm('cfp.view_event', is_event_visible | is_orga)
