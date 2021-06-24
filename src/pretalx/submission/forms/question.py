from django import forms
from django.db.models import Q
from django.utils.functional import cached_property

from pretalx.cfp.forms.cfp import CfPFormMixin
from pretalx.common.mixins.forms import QuestionFieldsMixin
from pretalx.submission.models import Question, QuestionTarget, QuestionVariant


class QuestionsForm(CfPFormMixin, QuestionFieldsMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        self.submission = kwargs.pop("submission", None)
        self.speaker = kwargs.pop("speaker", None)
        self.review = kwargs.pop("review", None)
        self.track = kwargs.pop("track", None) or getattr(
            self.submission, "track", None
        )
        self.submission_type = kwargs.pop("submission_type", None) or getattr(
            self.submission, "submission_type", None
        )
        self.target_type = kwargs.pop("target", QuestionTarget.SUBMISSION)
        self.for_reviewers = kwargs.pop("for_reviewers", False)
        if self.target_type == QuestionTarget.SUBMISSION:
            target_object = self.submission
        elif self.target_type == QuestionTarget.SPEAKER:
            target_object = self.speaker
        elif self.target_type == QuestionTarget.REVIEWER:
            target_object = self.review
        else:
            target_object = self.speaker
        readonly = kwargs.pop("readonly", False)

        super().__init__(*args, **kwargs)

        self.queryset = Question.all_objects.filter(event=self.event, active=True)
        if self.target_type:
            self.queryset = self.queryset.filter(target=self.target_type)
        else:
            self.queryset = self.queryset.exclude(target=QuestionTarget.REVIEWER)
        if self.track:
            self.queryset = self.queryset.filter(
                Q(tracks__in=[self.track]) | Q(tracks__isnull=True)
            )
        if self.submission_type:
            self.queryset = self.queryset.filter(
                Q(submission_types__in=[self.submission_type])
                | Q(submission_types__isnull=True)
            )
        if self.for_reviewers:
            self.queryset = self.queryset.filter(is_visible_to_reviewers=True)
        for question in self.queryset.prefetch_related("options"):
            initial_object = None
            initial = question.default_answer
            if target_object:
                answers = [
                    a
                    for a in target_object.answers.all()
                    if a.question_id == question.id
                ]
                if answers:
                    initial_object = answers[0]
                    initial = (
                        answers[0].answer_file
                        if question.variant == QuestionVariant.FILE
                        else answers[0].answer
                    )

            field = self.get_field(
                question=question,
                initial=initial,
                initial_object=initial_object,
                readonly=readonly,
            )
            field.question = question
            field.answer = initial_object
            self.fields[f"question_{question.pk}"] = field

    @cached_property
    def speaker_fields(self):
        return [
            forms.BoundField(self, field, name)
            for name, field in self.fields.items()
            if field.question.target == QuestionTarget.SPEAKER
        ]

    @cached_property
    def submission_fields(self):
        return [
            forms.BoundField(self, field, name)
            for name, field in self.fields.items()
            if field.question.target == QuestionTarget.SUBMISSION
        ]

    def save(self):
        for k, v in self.cleaned_data.items():
            self.save_questions(k, v)
