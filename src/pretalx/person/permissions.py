import rules


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
