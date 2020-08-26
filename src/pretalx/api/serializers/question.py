from rest_framework.serializers import ModelSerializer, SlugRelatedField

from pretalx.person.models import User
from pretalx.submission.models import Answer, AnswerOption, Question, Submission


class AnswerOptionSerializer(ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ("id", "answer")


class QuestionSerializer(ModelSerializer):
    options = AnswerOptionSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = (
            "id",
            "variant",
            "question",
            "required",
            "target",
            "options",
            "help_text",
            "default_answer",
            "contains_personal_data",
            "min_length",
            "max_length",
            "is_public",
            "is_visible_to_reviewers",
        )


class MinimalQuestionSerializer(ModelSerializer):
    class Meta:
        model = Question
        fields = ("id", "question")


class AnswerSerializer(ModelSerializer):
    question = MinimalQuestionSerializer(Question.objects.none(), read_only=True)
    submission = SlugRelatedField(queryset=Submission.objects.none(), slug_field="code")
    person = SlugRelatedField(queryset=User.objects.none(), slug_field="code")
    options = AnswerOptionSerializer(many=True)

    class Meta:
        model = Answer
        fields = (
            "id",
            "question",
            "answer",
            "answer_file",
            "submission",
            "person",
            "options",
        )
