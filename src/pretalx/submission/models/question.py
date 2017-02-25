from django.db import models

from pretalx.common.choices import Choices


class QuestionVariant(Choices):
    NUMBER = 'number'
    STRING = 'string'
    TEXT = 'text'
    BOOLEAN = 'boolean'
    CHOICES = 'choices'
    MULTIPLE = 'muliple_choice'

    valid_choices = [NUMBER, STRING, TEXT, BOOLEAN, CHOICES, MULTIPLE]


class Question(models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='questions',
    )
    variant = models.CharField(
        max_length=QuestionVariant.get_max_length(),
        choices=QuestionVariant.get_choices(),
    )
    question = models.CharField(
        max_length=200,
    )
    default_answer = models.TextField()
    required = models.BooleanField(
        default=False,
    )
    position = models.IntegerField(
        default=0,
    )


class AnswerOption(models.Model):
    question = models.ForeignKey(
        to='submission.Question',
        on_delete=models.PROTECT,
        related_name='options',
    )
    answer = models.CharField(
        max_length=200,
    )


class Answer(models.Model):
    question = models.ForeignKey(
        to='submission.Question',
        on_delete=models.PROTECT,
        related_name='answers',
    )
    submission = models.ForeignKey(
        to='submission.Submission',
        on_delete=models.PROTECT,
        related_name='answers',
    )
    answer = models.TextField()
    options = models.ManyToManyField(
        to='submission.AnswerOption',
        related_name='answers',
    )
