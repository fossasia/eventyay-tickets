import rules

from pretalx.submission.models.submission import SubmissionStates


@rules.predicate
def can_change_submissions(user, obj):
    event = getattr(obj, "event", None)
    if not user or user.is_anonymous or not obj or not event:
        return False
    return (
        user.is_administrator
        or event.teams.filter(members__in=[user], can_change_submissions=True).exists()
    )


def get_reviewer_teams(user, event):
    return event.teams.filter(members__in=[user], is_reviewer=True)


@rules.predicate
def is_reviewer(user, obj):
    event = getattr(obj, "event", None)
    if not user or user.is_anonymous or not obj or not event:
        return False
    return get_reviewer_teams(user, event).exists()


@rules.predicate
def is_administrator(user, obj):
    return getattr(user, "is_administrator", False)


@rules.predicate
def person_can_view_information(user, obj):
    event = obj.event
    qs = event.submissions.filter(speakers__in=[user])
    tracks = obj.limit_tracks.all()
    types = obj.limit_types.all()
    if tracks:
        qs = qs.filter(track__in=tracks)
    if types:
        qs = qs.filter(submission_type__in=types)
    if obj.target_group == "submitters":
        return qs.exists()
    if obj.target_group == "confirmed":
        return qs.filter(state=SubmissionStates.CONFIRMED).exists()
    return qs.filter(
        state__in=[SubmissionStates.CONFIRMED, SubmissionStates.ACCEPTED]
    ).exists()


rules.add_perm("person.is_administrator", is_administrator)
rules.add_perm(
    "person.view_information", can_change_submissions | person_can_view_information
)
rules.add_perm("person.change_information", can_change_submissions)
