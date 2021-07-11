from channels.db import database_sync_to_async
from django.db.models import Q

from venueless.core.models.poll import Poll, PollOption, PollVote


@database_sync_to_async
def create_poll(options, **kwargs):
    options = options or []
    new = Poll.objects.create(**{key: value for key, value in kwargs.items() if value})
    for option in options:
        PollOption.objects.create(poll=new, **option)
    new.refresh_from_db()
    return new.serialize_public()


@database_sync_to_async
def get_poll(pk, room):
    poll = Poll.objects.get(pk=pk, room=room)
    return poll.serialize_public()


@database_sync_to_async
def unpin_poll(room):
    room.polls.all().update(is_pinned=False)


@database_sync_to_async
def pin_poll(pk, room):
    room.polls.all().update(is_pinned=False)
    room.polls.filter(pk=pk).update(is_pinned=True)


@database_sync_to_async
def get_voted_polls(room, user):
    return list(
        Poll.objects.filter(room=room, options__votes__sender=user)
        .distinct()
        .values_list("id", flat=True)
    )


@database_sync_to_async
def get_polls(room, moderator=False, for_user=None, **kwargs):
    polls = Poll.objects.with_results().filter(room=room)
    if not moderator:
        polls = polls.filter(Q(state=Poll.States.OPEN) | Q(state=Poll.States.CLOSED))
    if kwargs:
        polls = polls.filter(**kwargs)
    if for_user:
        answers = (
            PollOption.objects.filter(votes__sender=for_user)
            .distinct()
            .values_list("id", flat=True)
        )
    return [
        poll.serialize_public(
            answers=answers.filter(poll=poll) if for_user else None,
            force_results=moderator,
        )
        for poll in polls
    ]


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
        PollOption.objects.filter(poll=poll, id__in=old_options - updated_options).delete()
        for option_kwargs in options:
            if "id" in option_kwargs:
                option = PollOption.objects.get(pk=option_kwargs["id"], poll=poll)
                for key, value in option_kwargs.items():
                    setattr(option, key, value)
                option.save()
            else:
                PollOption.objects.create(poll=poll, **option_kwargs)
    poll.refresh_from_db()
    return poll.serialize_public(force_results=True)


@database_sync_to_async
def delete_poll(**kwargs):
    Poll.objects.all().filter(pk=kwargs["id"], room=kwargs["room"]).delete()
    return True


@database_sync_to_async
def vote_on_poll(pk, room, user, options):
    poll = Poll.objects.get(pk=pk, room=room, state=Poll.States.OPEN)
    PollVote.objects.filter(sender=user, option__poll=poll).delete()
    validated_options = PollOption.objects.filter(
        poll=poll, id__in=options
    ).values_list("id", flat=True)
    PollVote.objects.bulk_create(
        [PollVote(sender=user, option_id=option) for option in validated_options]
    )
    return Poll.objects.get(pk=pk).serialize_public(
        force_results=True, answers=None
    )  # Do not send answers, as this object will be sent to everybody with access
