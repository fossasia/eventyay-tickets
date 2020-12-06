from channels.db import database_sync_to_async

from venueless.core.models.question import Question


@database_sync_to_async
def create_question(**kwargs):
    new = Question.objects.create(**kwargs)
    return new.serialize_public()


@database_sync_to_async
def get_question(pk, room):
    question = Question.objects.get(pk=pk, room=room)
    return question.serialize_public()


@database_sync_to_async
def update_question(moderator, room, **kwargs):
    question = Question.objects.get(pk=kwargs["id"], room=room)
    question.update(moderator=moderator, **kwargs)
    return question.serialize_public()
