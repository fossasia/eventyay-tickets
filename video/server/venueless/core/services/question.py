from channels.db import database_sync_to_async

from venueless.core.models.question import Question, QuestionSerializer


@database_sync_to_async
def create_question(**kwargs):
    new = Question.objects.create(**kwargs)
    return QuestionSerializer(new).data
