from channels.db import database_sync_to_async
from django.db.models import Exists, OuterRef, Q

from venueless.core.models.poll import Poll, PollOption, PollVote


@database_sync_to_async
def create_poll(options, **kwargs):
    options = options or []
    new = Poll.objects.create(**kwargs)
    for option in options:
        PollOption.objects.create(poll=new, **option)
    return new.refresh_from_db().serialize_public()


@database_sync_to_async
def get_poll(pk, room):
    poll = Poll.objects.with_results().get(pk=pk, room=room)
    return poll.serialize_public()


@database_sync_to_async
def pin_poll(pk, room):
    room.polls.all().update(is_pinned=False)
    room.polls.filter(pk=pk).update(is_pinned=True)


@database_sync_to_async
def get_polls(room, moderator=False, for_user=None, **kwargs):
    polls = Poll.objects.filter(room=room)
    if not moderator:
        polls = polls.filter(Q(state=Poll.States.OPEN) | Q(state=Poll.States.CLOSED))
    if kwargs:
        polls = polls.filter(**kwargs)
    if for_user:
        # TODO
        # subquery = QuestionVote.objects.filter(
        #    question_id=OuterRef("pk"), sender=for_user
        # )
        # polls = polls.annotate(_answer=Exists(subquery))
        pass
    return [poll.serialize_public(voted_state=bool(for_user)) for poll in polls]


@database_sync_to_async
def update_poll(**kwargs):
    poll = Poll.objects.get(pk=kwargs["id"], room=kwargs["room"])
    options = kwargs.pop("options", None)
    for key, value in kwargs.items():
        setattr(poll, key, value)
    poll.save()
    if options:
        for option_kwargs in options:
            option = PollOption.objects.get(pk=option_kwargs["id"], poll=poll)
            for key, value in option_kwargs.items():
                setattr(option, key, value)
            option.save()
    return poll.refresh_from_db().serialize_public()


@database_sync_to_async
def delete_poll(**kwargs):
    Poll.objects.all().filter(pk=kwargs["id"], room=kwargs["room"]).delete()
    return True


@database_sync_to_async
def vote_on_poll(pk, room, user, options):  # TODO validate option ids
    poll = Poll.objects.get(pk=pk, room=room)
    PollVote.objects.delete(sender=user, option__poll=poll)
    PollVote.objects.bulk_create(
        [PollVote(sender=user, option_id=option) for option in options]
    )
    return Poll.objects.with_with_results().get(pk=pk).serialize_public()
