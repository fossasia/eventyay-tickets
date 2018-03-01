import rules

from pretalx.submission.models.submission import SubmissionStates


@rules.predicate
def is_orga(user, obj):
    if not user or user.is_anonymous or not obj:
        return False
    from pretalx.person.models import EventPermission
    return user.is_administrator or EventPermission.objects.filter(
        user=user, event=obj.event, is_orga=True
    ).exists()


@rules.predicate
def is_reviewer(user, obj):
    if not user or user.is_anonymous or not obj:
        return False
    from pretalx.person.models import EventPermission
    return user.is_administrator or EventPermission.objects.filter(
        user=user, event=obj.event, is_reviewer=True
    ).exists()


@rules.predicate
def is_administrator(user, obj):
    return user.is_administrator


@rules.predicate
def person_can_view_information(user, obj):
    event = obj.event
    submissions = event.submissions.filter(speakers__in=[user])
    if obj.include_submitters:
        return submissions.exists()
    if obj.exclude_unconfirmed:
        return submissions.filter(state=SubmissionStates.CONFIRMED).exists()
    return submissions.filter(state__in=[SubmissionStates.CONFIRMED, SubmissionStates.ACCEPTED]).exists()


rules.add_perm('person.view_information', is_orga | person_can_view_information)
