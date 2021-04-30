from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager
from i18nfield.fields import I18nCharField

from pretalx.common.choices import Choices
from pretalx.common.mixins.models import FileCleanupMixin, LogMixin
from pretalx.common.phrases import phrases
from pretalx.common.urls import EventUrls
from pretalx.common.utils import path_with_hash


def answer_file_path(instance, filename):
    return f"{instance.question.event.slug}/question_uploads/{path_with_hash(filename)}"


class QuestionManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .exclude(active=False)
            .exclude(target=QuestionTarget.REVIEWER)
        )


class AllQuestionManager(models.Manager):
    pass


class QuestionVariant(Choices):
    NUMBER = "number"
    STRING = "string"
    TEXT = "text"
    BOOLEAN = "boolean"
    FILE = "file"
    CHOICES = "choices"
    MULTIPLE = "multiple_choice"

    valid_choices = [
        (NUMBER, _("Number")),
        (STRING, _("Text (one-line)")),
        (TEXT, _("Multi-line text")),
        (BOOLEAN, _("Yes/No")),
        (FILE, _("File upload")),
        (CHOICES, _("Choose one from a list")),
        (MULTIPLE, _("Choose multiple from a list")),
    ]


class QuestionTarget(Choices):
    SUBMISSION = "submission"
    SPEAKER = "speaker"
    REVIEWER = "reviewer"

    valid_choices = [
        (SUBMISSION, _("per proposal")),
        (SPEAKER, _("per speaker")),
        (REVIEWER, _("for reviewers")),
    ]


class QuestionRequired(Choices):
    NONE = "none"
    REQUIRE = "require"
    REQUIRE_AFTER = "require after"
    FREEZE_AFTER = "freeze after"

    valid_choices = [
        (NONE, _("always optional")),
        (REQUIRE, _("always required")),
        (REQUIRE_AFTER, _("require after deadline")),
        (FREEZE_AFTER, _("freeze after deadline")),
    ]


class Question(LogMixin, models.Model):
    """Questions can be asked per.

    :class:`~pretalx.submission.models.submission.Submission`, per speaker, or
    of reviewers per :class:`~pretalx.submission.models.review.Review`.

    Questions can have many types, which offers a flexible framework to give organisers
    the opportunity to get all the information they need.

    :param variant: Can be any of 'number', 'string', 'text', 'boolean',
        'file', 'choices', or 'multiple_choice'. Defined in the
        ``QuestionVariant`` class.
    :param target: Can be any of 'submission', 'speaker', or 'reviewer'.
        Defined in the ``QuestionTarget`` class.
    :param deadline: Datetime field. This field is required for 'require after' and 'freeze after' options of
        question_required field and optional for the other ones. For 'require after' it shows that the answer will
        be optional before the deadline and mandatory after that deadline. For 'freeze after' it shows that the
        answer will be allowed before the deadline and frozen after that deadline
    :param question_required: Can be any of 'none', 'require ', 'require after', or 'freeze after'.
        Defined in the ``QuestionRequired`` class.
        For 'always required' answering this question will always be required.
        For 'always optional' means that it will never be mandatory.
        For 'require after' the answer will be optional before the deadline and mandatory after the deadline.
        For 'freeze after' the answer will be allowed before the deadline and frozen after the deadline.
    :param position: Position in the question order in this event.
    """

    event = models.ForeignKey(
        to="event.Event", on_delete=models.PROTECT, related_name="questions"
    )
    variant = models.CharField(
        max_length=QuestionVariant.get_max_length(),
        choices=QuestionVariant.get_choices(),
        default=QuestionVariant.STRING,
    )
    target = models.CharField(
        max_length=QuestionTarget.get_max_length(),
        choices=QuestionTarget.get_choices(),
        default=QuestionTarget.SUBMISSION,
        verbose_name=_("question type"),
        help_text=_(
            "Do you require an answer from every speaker or for every session?"
        ),
    )

    deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("deadline"),
        help_text=_(
            "Set a deadline to make this question required or to freeze changes after the given date."
        ),
    )

    question_required = models.CharField(
        max_length=QuestionRequired.get_max_length(),
        choices=QuestionRequired.get_choices(),
        default=QuestionRequired.NONE,
        verbose_name=_("question required"),
        help_text=_(
            "By choosing 'always required' answering this question will always be required, "
            "while 'always optional' means that it will never be mandatory. "
            "On the other hand, for 'require after' and 'freeze after' options "
            "you will have to define a deadline. With 'require after', the answer will be optional"
            " before the deadline and mandatory after the deadline. With 'freeze after' the answer will be allowed "
            "before the deadline and frozen after the deadline"
        ),
    )

    tracks = models.ManyToManyField(
        to="submission.Track",
        related_name="questions",
        help_text=_(
            "You can limit this question to some tracks. Leave this field empty to apply to all tracks."
        ),
        verbose_name=_("Tracks"),
        blank=True,
    )
    submission_types = models.ManyToManyField(
        to="submission.SubmissionType",
        related_name="questions",
        help_text=_(
            "You can limit this question to some session types. Leave this field empty to apply to all session types."
        ),
        verbose_name=_("Session Types"),
        blank=True,
    )
    question = I18nCharField(max_length=800, verbose_name=_("question"))
    help_text = I18nCharField(
        null=True,
        blank=True,
        max_length=800,
        verbose_name=_("help text"),
        help_text=_("Will appear just like this text below the question input field.")
        + " "
        + phrases.base.use_markdown,
    )
    default_answer = models.TextField(
        null=True, blank=True, verbose_name=_("default answer")
    )
    position = models.IntegerField(default=0, verbose_name=_("position"))
    active = models.BooleanField(
        default=True,
        verbose_name=_("active"),
        help_text=_("Inactive questions will no longer be asked."),
    )
    contains_personal_data = models.BooleanField(
        default=True,
        verbose_name=_("Answers contain personal data"),
        help_text=_(
            "If a user deletes their account, answers of questions for personal data will be removed, too."
        ),
    )
    min_length = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Minimum text length"),
        help_text=_(
            "Minimum allowed text in characters or words (set in CfP settings)."
        ),
    )
    max_length = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Maximum text length"),
        help_text=_(
            "Maximum allowed text length in characters or words (set in CfP settings)."
        ),
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name=_("Publish answers"),
        help_text=_(
            "Answers will be shown on session or speaker pages as appropriate. Please note that you cannot make a question public after the first answers have been given, to allow speakers explicit consent before publishing information."
        ),
    )
    is_visible_to_reviewers = models.BooleanField(
        default=True,
        verbose_name=_("Show answers to reviewers"),
        help_text=_(
            "Should answers to this question be shown to reviewers? This is helpful if you want to collect personal information, but use anonymous reviews."
        ),
    )
    objects = ScopedManager(event="event", _manager_class=QuestionManager)
    all_objects = ScopedManager(event="event", _manager_class=AllQuestionManager)

    @property
    def required(self):

        now = timezone.now()
        if self.question_required == QuestionRequired.REQUIRE:
            require_question = True
        elif self.question_required == QuestionRequired.REQUIRE_AFTER:
            if self.deadline > now:
                require_question = False
            else:
                require_question = True
        else:
            require_question = False
        # Question should become optional in order to be frozen
        if self.freeze_after and (self.freeze_after <= now):
            require_question = False

        return require_question

    @property
    def disabled(self):
        now = timezone.now()
        disable_question = False
        # If deadline of freeze after has passed, disable question
        if self.freeze_after and (self.freeze_after <= now):
            disable_question = True
        return disable_question

    class urls(EventUrls):
        base = "{self.event.cfp.urls.questions}{self.pk}/"
        edit = "{base}edit"
        up = "{base}up"
        down = "{base}down"
        delete = "{base}delete"
        toggle = "{base}toggle"

    def __str__(self):
        return str(self.question)

    def missing_answers(
        self, filter_speakers: list = False, filter_talks: list = False
    ) -> int:
        """Returns how many answers are still missing or this question.

        This method only supports submission questions and speaker questions.
        For missing reviews, please use the Review.find_missing_reviews method.

        :param filter_speakers: Apply only to these speakers.
        :param filter_talks: Apply only to these talks.
        """
        from pretalx.person.models import User
        from pretalx.submission.models import Submission

        answers = self.answers.all()
        filter_talks = filter_talks or Submission.objects.none()
        filter_speakers = filter_speakers or User.objects.none()
        if filter_speakers or filter_talks:
            answers = answers.filter(
                models.Q(person__in=filter_speakers)
                | models.Q(submission__in=filter_talks)
            )
        answer_count = answers.count()
        if self.target == QuestionTarget.SUBMISSION:
            submissions = filter_talks or self.event.submissions.all()
            return max(submissions.count() - answer_count, 0)
        if self.target == QuestionTarget.SPEAKER:
            users = filter_speakers or User.objects.filter(
                submissions__event_id=self.event.pk
            )
            return max(users.count() - answer_count, 0)
        return 0

    class Meta:
        ordering = ["position"]


class AnswerOption(LogMixin, models.Model):
    """Provides the possible answers for.

    :class:`~pretalx.submission.models.question.Question` objects of variant
    'choice' or 'multiple_choice'.
    """

    question = models.ForeignKey(
        to="submission.Question", on_delete=models.PROTECT, related_name="options"
    )
    answer = I18nCharField(max_length=200)

    objects = ScopedManager(event="question__event")

    @cached_property
    def event(self):
        return self.question.event

    def __str__(self):
        """Used in choice forms."""
        return str(self.answer)


class Answer(LogMixin, FileCleanupMixin, models.Model):
    """Answers are connected to a.

    :class:`~pretalx.submission.models.question.Question`, and, depending on
    type, a :class:`~pretalx.person.models.user.User`, a
    :class:`~pretalx.submission.models.submission.Submission`, or a
    :class:`~pretalx.submission.models.review.Review`.
    """

    question = models.ForeignKey(
        to="submission.Question", on_delete=models.PROTECT, related_name="answers"
    )
    submission = models.ForeignKey(
        to="submission.Submission",
        on_delete=models.PROTECT,
        related_name="answers",
        null=True,
        blank=True,
    )
    person = models.ForeignKey(
        to="person.User",
        on_delete=models.PROTECT,
        related_name="answers",
        null=True,
        blank=True,
    )
    review = models.ForeignKey(
        to="submission.Review",
        on_delete=models.PROTECT,
        related_name="answers",
        null=True,
        blank=True,
    )
    answer = models.TextField()
    answer_file = models.FileField(upload_to=answer_file_path, null=True, blank=True)
    options = models.ManyToManyField(
        to="submission.AnswerOption", related_name="answers"
    )

    objects = ScopedManager(event="question__event")

    @cached_property
    def event(self):
        return self.question.event

    def __str__(self):
        """Help when debugging."""
        return f"Answer(question={self.question.question}, answer={self.answer})"

    def remove(self, person=None, force=False):
        """Deletes an answer."""
        for option in self.options.all():
            option.answers.remove(self)
        self.delete()

    remove.alters_data = True

    @cached_property
    def boolean_answer(self):
        if self.answer == "True":
            return True
        if self.answer == "False":
            return False

    @property
    def answer_string(self):
        if self.question.variant in ("number", "string", "text"):
            return self.answer or ""
        if self.question.variant == "boolean":
            if self.boolean_answer is True:
                return _("Yes")
            if self.boolean_answer is False:
                return _("No")
            return ""
        if self.question.variant == "file":
            return self.answer_file.url if self.answer_file else ""
        if self.question.variant in ("choices", "multiple_choice"):
            return ", ".join(str(option.answer) for option in self.options.all())

    @property
    def is_answered(self):
        return bool(self.answer_string)
