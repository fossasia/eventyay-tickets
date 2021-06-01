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
    # TODO: do we want to block updates after close/archive?
    poll = Poll.objects.get(pk=kwargs["id"], room=kwargs["room"])
    options = kwargs.pop("options", None)
    for key, value in kwargs.items():
        setattr(poll, key, value)
    poll.save()
    if options:
        old_options = set(poll.options.all().values_list("id", flat=True))
        updated_options = set(option["id"] for option in options if option.get("id"))
        PollOption.objects.delete(poll=poll, id__in=old_options - updated_options)
        for option_kwargs in options:
            if "id" in option_kwargs:
                option = PollOption.objects.get(pk=option_kwargs["id"], poll=poll)
                for key, value in option_kwargs.items():
                    setattr(option, key, value)
                option.save()
            else:
                PollOption.objects.create(poll=poll, **option_kwargs)
    return poll.refresh_from_db().serialize_public()


@database_sync_to_async
def delete_poll(**kwargs):
    Poll.objects.all().filter(pk=kwargs["id"], room=kwargs["room"]).delete()
    return True


@database_sync_to_async
def vote_on_poll(pk, room, user, options):
    poll = Poll.objects.get(pk=pk, room=room)
    PollVote.objects.delete(sender=user, option__poll=poll)
    validated_options = PollOption.objects.filter(poll=poll, id__in=options)
    PollVote.objects.bulk_create(
        [PollVote(sender=user, option_id=option) for option in validated_options]
    )
    return Poll.objects.with_with_results().get(pk=pk).serialize_public()
