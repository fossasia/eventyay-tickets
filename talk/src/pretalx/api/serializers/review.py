from rest_flex_fields.serializers import FlexFieldsSerializerMixin
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import SlugRelatedField

from pretalx.api.mixins import PretalxSerializer
from pretalx.api.serializers.question import AnswerSerializer
from pretalx.api.versions import CURRENT_VERSIONS, register_serializer
from pretalx.person.models import User
from pretalx.submission.models import (
    Review,
    ReviewScore,
    ReviewScoreCategory,
    Submission,
)


@register_serializer(versions=CURRENT_VERSIONS)
class ReviewScoreCategorySerializer(PretalxSerializer):
    class Meta:
        model = ReviewScoreCategory
        fields = (
            "id",
            "name",
            "weight",
            "required",
            "active",
            "limit_tracks",
            "is_independent",
        )
        expandable_fields = {
            "limit_tracks": (
                "pretalx.api.serializers.submission.TrackSerializer",
                {"read_only": True, "many": True},
            ),
        }


@register_serializer(versions=CURRENT_VERSIONS)
class ReviewScoreSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    class Meta:
        model = ReviewScore
        fields = ("id", "category", "value", "label")
        expandable_fields = {
            "category": (
                "pretalx.api.serializers.review.ReviewScoreCategorySerializer",
                {"read_only": True},
            ),
        }


@register_serializer(versions=CURRENT_VERSIONS)
class ReviewerSerializer(PretalxSerializer):
    class Meta:
        model = User
        fields = ("code", "name", "email")


@register_serializer(versions=CURRENT_VERSIONS)
class ReviewWriteSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    submission = SlugRelatedField(slug_field="code", queryset=Submission.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["answers"].required = False
        self.fields["score"].read_only = True
        if self.event:
            self.fields["scores"].queryset = ReviewScore.objects.filter(
                category__event=self.event
            )
            self.fields["text"].required = self.event.review_settings["text_mandatory"]
            self.fields["scores"].required = self.event.review_settings[
                "score_mandatory"
            ]
        if submissions := self.context.get("submissions"):
            self.fields["submission"].queryset = submissions

    class Meta:
        model = Review
        fields = [
            "id",
            "submission",
            "text",
            "score",
            "scores",
            "answers",
        ]
        read_only_fields = ("submission",)
        expandable_fields = {
            "submission": (
                "pretalx.api.serializers.submission.SubmissionSerializer",
                {"read_only": True, "omit": ("slots",)},
            ),
            "answers": (
                "pretalx.api.serializers.question.AnswerSerializer",
                {"read_only": True, "many": True},
            ),
            "user": (
                "pretalx.api.serializers.review.ReviewerSerializer",
                {"read_only": True},
            ),
            "scores": (
                "pretalx.api.serializers.review.ReviewScoreSerializer",
                {"read_only": True, "many": True},
            ),
        }

    def validate_scores(self, value):
        if not len(value) == len(set([s.category for s in value])):
            raise ValidationError("You can only assign one score per category!")
        return value

    def validate_submission(self, value):
        if self.event.reviews.filter(
            user=self.context["request"].user, submission=value
        ).exists():
            raise ValidationError("You have already reviewed this submission.")
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        scores = validated_data.pop("scores", None)
        instance = super().create(validated_data)
        if scores:
            instance.scores.set(scores)
            instance.save(update_score=True)
        return instance

    def update(self, instance, validated_data):
        validated_data["user"] = self.context["request"].user
        scores = validated_data.pop("scores", None)
        instance = super().update(instance, validated_data)
        if scores:
            instance.scores.set(scores)
            instance.save(update_score=True)
        return instance


@register_serializer(versions=CURRENT_VERSIONS)
class ReviewSerializer(ReviewWriteSerializer):
    scores = ReviewScoreSerializer(many=True)
    user = SlugRelatedField(slug_field="code", read_only=True)
    answers = AnswerSerializer(read_only=True, many=True)

    class Meta(ReviewWriteSerializer.Meta):
        fields = ReviewWriteSerializer.Meta.fields + ["user"]
