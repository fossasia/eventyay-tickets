from django.db import models
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField
from urlman import Urls

from pretalx.common.choices import Choices
from pretalx.common.mixins import LogMixin


class QuestionVariant(Choices):
    NUMBER = 'number'
    STRING = 'string'
    TEXT = 'text'
    BOOLEAN = 'boolean'
    CHOICES = 'choices'
    MULTIPLE = 'muliple_choice'

    valid_choices = [
        (NUMBER, _('number')),
        (STRING, _('one-line text')),
        (TEXT, _('multi-line text')),
        (BOOLEAN, _('yes/no')),
        (CHOICES, _('single choice')),
        (MULTIPLE, _('multiple choice'))
    ]


class Question(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='questions',
    )
    variant = models.CharField(
        max_length=QuestionVariant.get_max_length(),
        choices=QuestionVariant.get_choices(),
        default=QuestionVariant.STRING,
    )
    question = I18nCharField(
        max_length=200,
        verbose_name=_('question'),
    )
    default_answer = models.TextField(
        null=True, blank=True,
        verbose_name=_('default answer'),
    )
    required = models.BooleanField(
        default=False,
        verbose_name=_('required'),
    )
    position = models.IntegerField(
        default=0,
        verbose_name=_('position'),
    )

    class urls(Urls):
        base = '{self.event.cfp.urls.questions}/{self.pk}'
        edit = '{base}/edit'
        delete = '{base}/delete'

    def __str__(self):
        return str(self.question)

    class Meta:
        ordering = ['position']


class AnswerOption(LogMixin, models.Model):
    question = models.ForeignKey(
        to='submission.Question',
        on_delete=models.PROTECT,
        related_name='options',
    )
    answer = I18nCharField(
        max_length=200,
    )

    @property
    def event(self):
        return self.question.event

    def __str__(self):
        return str(self.answer)


class Answer(LogMixin, models.Model):
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

    @property
    def event(self):
        return self.question.event

    def __str__(self):
        return self.answer
