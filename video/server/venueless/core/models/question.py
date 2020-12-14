import uuid
from functools import cached_property

from django.db import models


class QuestionManager(models.Manager):
    def with_score(self):
        return self.get_queryset().annotate(_score=models.Count("votes"))


class Question(models.Model):
    class States(models.TextChoices):
        VISIBLE = "visible"
        MOD_QUEUE = "mod_queue"  # This question is waiting to be moderated
        ARCHIVED = "archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    content = models.TextField()
    state = models.CharField(
        default=States.MOD_QUEUE, choices=States.choices, max_length=10
    )
    answered = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    room = models.ForeignKey(
        to="Room",
        related_name="questions",
        on_delete=models.CASCADE,
    )
    sender = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="questions",
    )
    moderator = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderated_questions",
    )

    objects = QuestionManager()

    @cached_property
    def score(self):
        # When the question is retrieved with the with_score manager method,
        # we can just use the available score. We'll count manually otherwise.
        aggregated_score = getattr(self, "_score", None)
        if aggregated_score is not None:
            return aggregated_score
        return self.votes.all().count()

    def serialize_public(self):
        return {
            "id": str(self.id),
            "content": self.content,
            "state": self.state,
            "answered": self.answered,
            "timestamp": self.timestamp.isoformat(),
            "room_id": str(self.room_id),
            "score": self.score or 0,
        }


class QuestionVote(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="votes"
    )
    sender = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="question_votes",
    )
