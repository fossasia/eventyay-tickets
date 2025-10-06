import uuid
from functools import cached_property

from django.db import models


class PollManager(models.Manager):
    def with_results(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(
                models.Prefetch(
                    "options",
                    queryset=PollOption.objects.all()
                    .order_by("order")
                    .annotate(_votes=models.Count("votes")),
                )
            )
        )


class Poll(models.Model):
    class States(models.TextChoices):
        DRAFT = "draft"
        OPEN = "open"
        CLOSED = "closed"
        ARCHIVED = "archived"

    class Types(models.TextChoices):
        CHOICE = "choice"
        MULTI_CHOICE = "multi"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    content = models.TextField()
    state = models.CharField(default=States.DRAFT, choices=States.choices, max_length=8)
    poll_type = models.CharField(
        default=Types.CHOICE, choices=Types.choices, max_length=6
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    is_pinned = models.BooleanField(default=False)
    cached_results = models.JSONField(null=True, blank=True)

    room = models.ForeignKey(
        to="Room",
        related_name="polls",
        on_delete=models.CASCADE,
    )

    objects = PollManager()

    def save(self, *args, **kwargs):
        if self.state in (self.States.CLOSED, self.States.ARCHIVED):
            if not self.cached_results:
                self.cached_results = self.get_results()
        else:
            self.cached_results = None
        return super().save(*args, **kwargs)

    def get_results(self):
        options = self.options.all()
        if not options:
            return []
        if hasattr(options[0], "_votes"):  # Comes via .with_results()
            return {str(option.pk): option._votes for option in options}
        else:
            return {
                str(option.pk): option._votes
                for option in self.options.all().annotate(_votes=models.Count("votes"))
            }

    @cached_property
    def results(self):
        if self.cached_results:
            return self.cached_results
        # When the poll is retrieved with the with_results manager method,
        # we can just use the available score. We'll count manually otherwise.
        results = getattr(self, "_results", None)
        if results is not None:
            return results
        return self.get_results()

    def serialize_public(self, answers=None, force_results=False):
        """
        Results are always returned when force_results is given.
        Otherwise, results are returned for closed polls or when answers are present.
        """
        data = {
            "id": str(self.id),
            "content": self.content,
            "state": self.state,
            "timestamp": self.timestamp.isoformat(),
            "room_id": str(self.room_id),
            "is_pinned": self.is_pinned,
            "options": [
                {
                    "id": str(option.id),
                    "content": option.content,
                    "order": option.order,
                }
                for option in self.options.all()
            ],
        }
        if force_results or self.state != self.States.OPEN or answers:
            # If the poll is closed, everybody may see the results
            # If it is in draft/archived states, the only people who can see it at all,
            # can also see the results.
            data["results"] = self.results
        if answers:
            data["answers"] = list(str(a) for a in answers)
        return data


class PollOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    order = models.IntegerField(default=1)
    content = models.TextField()

    class Meta:
        ordering = ["order"]


class PollVote(models.Model):
    option = models.ForeignKey(
        PollOption, on_delete=models.CASCADE, related_name="votes"
    )
    sender = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="poll_votes",
    )

    class Meta:
        unique_together = (("option", "sender"),)
