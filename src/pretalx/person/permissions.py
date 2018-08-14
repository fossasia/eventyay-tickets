import rules

from pretalx.submission.models.submission import SubmissionStates


@rules.predicate
def can_change_submissions(user, obj):
    if not user or user.is_anonymous or not obj or not hasattr(obj, 'event'):
        return False
    return user.is_administrator or obj.event in user.get_events_for_permission(can_change_submissions=True)


@rules.predicate
def is_reviewer(user, obj):
    event = getattr(obj, 'event', None)
    if not user or user.is_anonymous or not obj or not event:
        return False
    return event in user.get_events_for_permission(is_reviewer=True)


@rules.predicate
def is_administrator(user, obj):
    return getattr(user, 'is_administrator', False)


@rules.predicate
def person_can_view_information(user, obj):
    event = obj.event
    submissions = event.submissions.filter(speakers__in=[user])
    if obj.include_submitters:
        return submissions.exists()
    if obj.exclude_unconfirmed:
        return submissions.filter(state=SubmissionStates.CONFIRMED).exists()
    return submissions.filter(state__in=[SubmissionStates.CONFIRMED, SubmissionStates.ACCEPTED]).exists()


rules.add_perm('person.view_information', can_change_submissions | person_can_view_information)
rules.add_perm('person.change_information', can_change_submissions)
