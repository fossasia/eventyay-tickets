import rules

from pretalx.person.permissions import can_change_submissions


@rules.predicate
def is_agenda_visible(user, event):
    return bool(
        event
        and event.is_public
        and event.settings.show_schedule
        and event.current_schedule
    )


@rules.predicate
def is_widget_always_visible(user, event):
    return event.settings.show_widget_if_not_public


@rules.predicate
def has_agenda(user, event):
    return bool(event.current_schedule)


@rules.predicate
def is_sneak_peek_visible(user, event):
    return bool(event and event.is_public and event.settings.show_sneak_peek)


@rules.predicate
def is_submission_visible(user, submission):
    if hasattr(submission, 'submission'):
        submission = submission.submission
    return bool(
        submission
        and is_agenda_visible(user, submission.event)
        and submission.slots.filter(schedule=submission.event.current_schedule, is_visible=True).exists()
    )


@rules.predicate
def is_feedback_ready(user, submission):
    return bool(
        submission
        and is_submission_visible(user, submission)
        and submission.does_accept_feedback
    )


@rules.predicate
def is_speaker_viewable(user, profile):
    if not profile:
        return False
    is_speaker = profile.user.submissions.filter(
        slots__schedule=profile.event.current_schedule
    ).exists()
    return is_speaker and is_agenda_visible(user, profile.event)


rules.add_perm(
    'agenda.view_schedule', (has_agenda & is_agenda_visible) | can_change_submissions
)
rules.add_perm(
    'agenda.view_sneak_peek',
    ((~is_agenda_visible | ~has_agenda) & is_sneak_peek_visible)
    | can_change_submissions,
)
rules.add_perm('agenda.view_slot', is_submission_visible | can_change_submissions)
rules.add_perm('agenda.view_speaker', is_speaker_viewable | can_change_submissions)
rules.add_perm('agenda.give_feedback', is_feedback_ready)
rules.add_perm('agenda.view_widget', is_agenda_visible | is_widget_always_visible)
