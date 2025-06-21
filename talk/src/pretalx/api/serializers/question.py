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
            "question_required",
            "deadline",
            "required",
            "read_only",
            "freeze_after",
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


class AnswerWriteSerializer(ModelSerializer):
    submission = SlugRelatedField(
        queryset=Submission.objects.none(),
        slug_field="code",
        required=False,
        style={"input_type": "text", "base_template": "input.html"},
    )
    person = SlugRelatedField(
        queryset=User.objects.all(),
        slug_field="code",
        required=False,
        style={"input_type": "text", "base_template": "input.html"},
    )
    options = AnswerOptionSerializer(many=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request:
            return
        self.fields["question"].queryset = request.event.questions.all()
        self.fields["submission"].queryset = request.event.submissions.all()
        self.fields["review"].queryset = request.event.reviews.all()
        self.fields["review"].style = {
            "input_type": "number",
            "base_template": "input.html",
        }
        self.fields["question"].style = {
            "input_type": "number",
            "base_template": "input.html",
        }

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


class AnswerSerializer(AnswerWriteSerializer):
    question = MinimalQuestionSerializer(Question.objects.none())

    class Meta(AnswerWriteSerializer.Meta):
        pass
