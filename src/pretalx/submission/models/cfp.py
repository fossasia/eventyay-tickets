from django.db import models


class CfP(models.Model):
    event = models.OneToOneField(
        to='event.Event',
        on_delete=models.PROTECT,
    )
    headline = models.CharField(
        max_length=300,
        null=True, blank=True,
    )
    text = models.TextField(null=True, blank=True)
    default_type = models.ForeignKey(
        to='submission.SubmissionType',
        on_delete=models.PROTECT,
        related_name='+',
    )
    deadline = models.DateTimeField(null=True, blank=True)
    # languages

    def __str__(self) -> str:
        return str(self.headline)
