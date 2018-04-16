import rules

from pretalx.person.permissions import can_change_submissions


@rules.predicate
def is_agenda_visible(user, event):
    return bool(event and event.is_public and event.settings.show_schedule)


@rules.predicate
def is_slot_visible(user, slot):
    return bool(slot and is_agenda_visible(user, slot.submission.event) and slot.is_visible)


@rules.predicate
def is_feedback_ready(user, submission):
    return bool(submission and is_slot_visible(user, submission.slot) and submission.does_accept_feedback)


@rules.predicate
def is_speaker_viewable(user, profile):
    is_speaker = profile.user.submissions.filter(slots__schedule=profile.event.current_schedule).exists()
    return is_speaker and is_agenda_visible(user, profile.event)


rules.add_perm('agenda.view_schedule', is_agenda_visible | can_change_submissions)
rules.add_perm('agenda.view_slot', is_slot_visible | can_change_submissions)
rules.add_perm('agenda.view_speaker', is_speaker_viewable | can_change_submissions)
rules.add_perm('agenda.give_feedback', is_feedback_ready)
