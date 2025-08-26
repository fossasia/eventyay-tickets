from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Answer
from eventyay.common.exporter import BaseExporter, CSVExporterMixin
from eventyay.common.signals import register_data_exporters


class SpeakerQuestionData(CSVExporterMixin, BaseExporter):
    identifier = 'speaker-questions.csv'
    public = False
    icon = 'fa-question-circle'
    cors = '*'
    group = 'speaker'

    @property
    def verbose_name(self):
        return _('Custom fields data') + ' (' + _('speakers') + ')'

    @property
    def filename(self):
        return f'{self.event.slug}-speaker-questions.csv'

    def get_data(self, **kwargs):
        field_names = ['code', 'name', 'email', 'question', 'answer']
        data = []
        qs = (
            Answer.objects.filter(
                question__target='speaker',
                question__event=self.event,
                question__active=True,
                person__isnull=False,
            )
            .select_related('question', 'person')
            .order_by('person__name')
        )
        for answer in qs:
            data.append(
                {
                    'code': answer.person.code,
                    'name': answer.person.name,
                    'email': answer.person.email,
                    'question': answer.question.question,
                    'answer': answer.answer_string,
                }
            )
        return field_names, data


@receiver(register_data_exporters, dispatch_uid='exporter_builtin_speaker_question')
def register_speaker_question_exporter(sender, **kwargs):
    return SpeakerQuestionData


class SubmissionQuestionData(CSVExporterMixin, BaseExporter):
    identifier = 'submission-questions.csv'
    public = False
    icon = 'fa-question-circle-o'
    cors = '*'

    @property
    def verbose_name(self):
        return _('Custom fields data') + ' (' + _('submissions') + ')'

    @property
    def filename(self):
        return f'{self.event.slug}-submission-questions.csv'

    def get_data(self, **kwargs):
        field_names = ['code', 'title', 'question', 'answer']
        data = []
        qs = Answer.objects.filter(
            question__target='submission',
            question__event=self.event,
            question__active=True,
        ).order_by('submission__title')
        for answer in qs:
            data.append(
                {
                    'code': answer.submission.code,
                    'title': answer.submission.title,
                    'question': answer.question.question,
                    'answer': answer.answer_string,
                }
            )
        return field_names, data


@receiver(register_data_exporters, dispatch_uid='exporter_builtin_submission_question')
def register_submission_question_exporter(sender, **kwargs):
    return SubmissionQuestionData
