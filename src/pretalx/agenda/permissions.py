import rules

from pretalx.person.permissions import can_change_submissions


@rules.predicate
def is_agenda_visible(user, event):
    return bool(
        event
        and event.is_public
        and event.feature_flags["show_schedule"]
        and event.current_schedule
    )


@rules.predicate
def is_widget_always_visible(user, event):
    return event.feature_flags["show_widget_if_not_public"]


@rules.predicate
def has_agenda(user, event):
    return bool(event.current_schedule)


@rules.predicate
def are_featured_submissions_visible(user, event):
    if (
        not event
        or not event.is_public
        or event.feature_flags["show_featured"] == "never"
    ):
        return False
    if event.feature_flags["show_featured"] == "always":
        return True
    return (not is_agenda_visible(user, event)) or (not has_agenda(user, event))


def is_submission_visible_via_schedule(user, submission):
    return bool(
        submission
        and is_agenda_visible(user, submission.event)
        and submission.slots.filter(
            schedule=submission.event.current_schedule, is_visible=True
        ).exists()
    )


def is_submission_visible_via_featured(user, submission):
    return bool(
        submission
        and submission.is_featured
        and are_featured_submissions_visible(user, submission.event)
    )


@rules.predicate
def is_submission_visible(user, submission):
    submission = getattr(submission, "submission", submission)
    if not submission:
        return False
    return is_submission_visible_via_schedule(
        user, submission
    ) or is_submission_visible_via_featured(user, submission)


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
    "agenda.view_schedule", (has_agenda & is_agenda_visible) | can_change_submissions
)
rules.add_perm(
    "agenda.view_featured_submissions",
    are_featured_submissions_visible | can_change_submissions,
)
rules.add_perm("agenda.view_submission", is_submission_visible | can_change_submissions)
rules.add_perm("agenda.view_speaker", is_speaker_viewable | can_change_submissions)
rules.add_perm("agenda.give_feedback", is_feedback_ready)
rules.add_perm(
    "agenda.view_widget",
    is_agenda_visible | is_widget_always_visible | can_change_submissions,
)
