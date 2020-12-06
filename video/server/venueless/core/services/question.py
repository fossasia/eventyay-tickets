from channels.db import database_sync_to_async

from venueless.core.models.question import Question, QuestionSerializer


@database_sync_to_async
def create_question(**kwargs):
    new = Question.objects.create(**kwargs)
    return QuestionSerializer(new).data


@database_sync_to_async
def get_question(pk, room):
    question = Question.objects.get(pk=pk, room=room)
    return QuestionSerializer(question).data


@database_sync_to_async
def update_question(moderator, room, **kwargs):
    question = Question.objects.get(pk=kwargs["id"], room=room)
    question.update(moderator=moderator, **kwargs)
    return QuestionSerializer(question).data
