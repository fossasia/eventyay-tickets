import datetime as dt

import rules
from django.utils.timezone import now


@rules.predicate
def is_administrator(user, obj):
    return getattr(user, "is_administrator", False)


@rules.predicate
def is_reviewer(user, obj):
    event = getattr(obj, "event", None)
    if not user or user.is_anonymous or not obj or not event:
        return False
    # We’re not using get_permissions_for_event here, as this will always return
    # the full permission set for administrators, but we want to explicitly check
    # for team membership
    return user in event.reviewers


@rules.predicate
def is_only_reviewer(user, obj):
    return user.get_permissions_for_event(obj.event) == {"is_reviewer"}


@rules.predicate
def can_mark_speakers_arrived(user, obj):
    event = obj.event
    return (event.date_from - dt.timedelta(days=3)) <= now().date() <= event.date_to


@rules.predicate
def can_view_information(user, obj):
    from pretalx.submission.models.submission import SubmissionStates

    event = obj.event
    qs = event.submissions.filter(speakers__in=[user])
    if tracks := obj.limit_tracks.all():
        qs = qs.filter(track__in=tracks)
    if types := obj.limit_types.all():
        qs = qs.filter(submission_type__in=types)
    if obj.target_group == "submitters":
        return qs.exists()
    if obj.target_group == "confirmed":
        return qs.filter(state=SubmissionStates.CONFIRMED).exists()
    return qs.filter(state__in=SubmissionStates.accepted_states).exists()
