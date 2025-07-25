from django.db import transaction
from rest_flex_fields.serializers import FlexFieldsSerializerMixin
from rest_framework import exceptions
from rest_framework.serializers import PrimaryKeyRelatedField, SlugRelatedField

from pretalx.api.mixins import PretalxSerializer
from pretalx.api.serializers.fields import UploadedFileField
from pretalx.api.versions import CURRENT_VERSIONS, register_serializer
from pretalx.person.models import User
from pretalx.submission.models import (
    Answer,
    AnswerOption,
    Question,
    QuestionTarget,
    QuestionVariant,
    Review,
    Submission,
    SubmissionType,
    Track,
)
from pretalx.submission.rules import questions_for_user


@register_serializer(versions=CURRENT_VERSIONS)
class AnswerOptionSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    question = PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = AnswerOption
        fields = ("id", "question", "answer", "position")
        expandable_fields = {
            "question": (
                "pretalx.api.serializers.question.QuestionSerializer",
                {"read_only": True, "omit": ["options"]},
            )
        }


# This serializer exists mostly for documentation purposes, as otherwise
# drf_spectacular will not pick up that questions can be set on create,
# but not changed on update. And if we have a separate serializer already,
# we might as well use it to isolate the create action fully.
@register_serializer(versions=CURRENT_VERSIONS)
class AnswerOptionCreateSerializer(AnswerOptionSerializer):
    question = PrimaryKeyRelatedField(read_only=False, queryset=Question.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = kwargs.get("context", {}).get("request")
        if request and hasattr(request, "event"):
            self.fields["question"].queryset = request.event.questions(
                manager="all_objects"
            ).filter(
                variant__in=[
                    QuestionVariant.CHOICES,
                    QuestionVariant.MULTIPLE,
                ]
            )
        else:
            self.fields["question"].queryset = Question.objects.none()

    class Meta(AnswerOptionSerializer.Meta):
        expandable_fields = None


@register_serializer(versions=CURRENT_VERSIONS)
class QuestionSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    class Meta:
        model = Question
        fields = (
            "id",
            "question",
            "help_text",
            "default_answer",
            "variant",
            "target",
            "deadline",
            "freeze_after",
            "question_required",
            "position",
            "tracks",
            "submission_types",
            "options",
            "min_length",
            "max_length",
            "min_number",
            "max_number",
            "min_date",
            "max_date",
            "min_datetime",
            "max_datetime",
        )
        expandable_fields = {
            "options": (
                "pretalx.api.serializers.question.AnswerOptionSerializer",
                {
                    "many": True,
                    "read_only": True,
                    "fields": ("id", "answer", "position"),
                },
            ),
            "tracks": (
                "pretalx.api.serializers.submission.TrackSerializer",
                {"many": True, "read_only": True},
            ),
            "submission_types": (
                "pretalx.api.serializers.submission.SubmissionTypeSerializer",
                {"many": True, "read_only": True},
            ),
        }


# Just for documentation purposes, as the docs will otherwise pick up the reduced
# fields also for the primary AnswerOptionSerializer, for some unholy reason.
class NestedAnswerOptionSerializer(AnswerOptionSerializer):
    pass


@register_serializer(versions=CURRENT_VERSIONS)
class QuestionOrgaSerializer(QuestionSerializer):
    options = NestedAnswerOptionSerializer(
        many=True, required=False, fields=("id", "answer", "position")
    )

    class Meta(QuestionSerializer.Meta):
        fields = QuestionSerializer.Meta.fields + (
            "active",
            "is_public",
            "contains_personal_data",
            "is_visible_to_reviewers",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = kwargs.get("context", {}).get("request")
        if request and hasattr(request, "event"):
            self.fields["tracks"].queryset = request.event.tracks.all()
            self.fields["submission_types"].queryset = (
                request.event.submission_types.all()
            )
        else:
            self.fields["tracks"].queryset = Track.objects.none()
            self.fields["submission_types"].queryset = SubmissionType.objects.none()

    def create(self, validated_data):
        options_data = validated_data.pop("options", None)
        validated_data["event"] = getattr(self.context.get("request"), "event", None)
        question = super().create(validated_data)
        if options_data:
            self._handle_options(question, options_data)
        return question

    def update(self, instance, validated_data):
        options_data = validated_data.pop("options", None)
        question = super().update(instance, validated_data)
        if options_data is not None:
            self._handle_options(question, options_data)
        return question

    def _handle_options(self, question, options_data):
        # Replace existing options
        with transaction.atomic():
            question.options.all().delete()
            for option_data in options_data:
                AnswerOption.objects.create(question=question, **option_data)


@register_serializer(versions=CURRENT_VERSIONS)
class AnswerSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    question = PrimaryKeyRelatedField(read_only=True)
    submission = SlugRelatedField(
        slug_field="code",
        read_only=True,
        required=False,
    )
    person = SlugRelatedField(
        slug_field="code",
        read_only=True,
        required=False,
    )
    review = PrimaryKeyRelatedField(read_only=True, required=False)
    answer_file = UploadedFileField(required=False)

    class Meta:
        model = Answer
        fields = (
            "id",
            "question",
            "answer",
            "answer_file",
            "submission",
            "review",
            "person",
            "options",
        )
        expandable_fields = {
            "question": (
                "pretalx.api.serializers.question.QuestionSerializer",
                {"read_only": True, "omit": ("options",)},
            ),
            "options": (
                "pretalx.api.serializers.question.AnswerOptionSerializer",
                {"many": True, "read_only": True, "omit": ("question",)},
            ),
            "person": (
                "pretalx.api.serializers.speaker.SpeakerSerializer",
                {"read_only": True, "omit": ("answers",)},
            ),
            # submissions and reviews are currently not expandable due to permissions
            # concerns: We’d have to make sure that users with access to e.g. some
            # submission answers and some review answers would only see the ones from
            # their assigned tracks or submissions.
        }


@register_serializer(versions=CURRENT_VERSIONS)
class AnswerCreateSerializer(AnswerSerializer):
    question = PrimaryKeyRelatedField(queryset=Question.objects.none())
    submission = SlugRelatedField(
        queryset=Submission.objects.none(),
        slug_field="code",
        required=False,
        allow_null=True,
    )
    person = SlugRelatedField(
        queryset=User.objects.none(),
        slug_field="code",
        required=False,
        allow_null=True,
    )
    review = PrimaryKeyRelatedField(
        queryset=Review.objects.none(),
        required=False,
        allow_null=True,
    )
    options = PrimaryKeyRelatedField(
        queryset=AnswerOption.objects.none(),
        required=False,
        many=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request or not getattr(request, "event", None):
            return
        self.fields["question"].queryset = questions_for_user(
            request.event, request.user
        )
        self.fields["submission"].queryset = request.event.submissions.all()
        self.fields["person"].queryset = User.objects.filter(
            submissions__event=request.event
        )
        self.fields["review"].queryset = request.event.reviews.all()

    def validate(self, data):
        question = self.get_with_fallback(data, "question")

        if question.variant in (QuestionVariant.CHOICES, QuestionVariant.MULTIPLE):
            options = self.get_with_fallback(data, "options")
            if not options:
                raise exceptions.ValidationError(
                    {
                        "options": "This field is required for choice or multiple-choice question."
                    }
                )
            for option in options:
                if option.question != question:
                    raise exceptions.ValidationError(
                        {
                            "options": f"Option {option.pk} does not belong to question {question.pk}."
                        }
                    )

        target = question.target
        submission = self.get_with_fallback(data, "submission")
        review = self.get_with_fallback(data, "review")
        person = self.get_with_fallback(data, "person")
        if target == QuestionTarget.SUBMISSION and not submission:
            raise exceptions.ValidationError(
                {"submission": "This field is required for submission questions."}
            )
        if target == QuestionTarget.REVIEWER and not review:
            raise exceptions.ValidationError(
                {"review": "This field is required for reviewer questions."}
            )
        if target == QuestionTarget.SPEAKER and not person:
            raise exceptions.ValidationError(
                {"person": "This field is required for speaker questions."}
            )

        # Only allow the field matching the question target
        if target == QuestionTarget.SUBMISSION and review:
            raise exceptions.ValidationError(
                {"review": "Cannot set review for submission question."}
            )
        if target == QuestionTarget.REVIEWER and submission:
            raise exceptions.ValidationError(
                {"submission": "Cannot set submission for reviewer question."}
            )
        if target == QuestionTarget.SPEAKER and submission:
            raise exceptions.ValidationError(
                {"submission": "Cannot set submission for speaker question."}
            )

        return data

    class Meta(AnswerSerializer.Meta):
        expandable_fields = None
