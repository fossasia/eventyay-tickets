from rest_framework.serializers import ModelSerializer, SlugRelatedField

from pretalx.person.models import User
from pretalx.submission.models import Answer, AnswerOption, Question, Submission


class AnswerOptionSerializer(ModelSerializer):

    class Meta:
        model = AnswerOption
        fields = ('id', 'answer')


class QuestionSerializer(ModelSerializer):
    options = AnswerOptionSerializer(many=True)

    class Meta:
        model = Question
        fields = ('id', 'question', 'required', 'target', 'options')


class AnswerSerializer(ModelSerializer):
    question = QuestionSerializer(Question.objects.all(), read_only=True)
    submission = SlugRelatedField(queryset=Submission.objects.all(), slug_field='code')
    person = SlugRelatedField(queryset=User.objects.all(), slug_field='code')
    options = AnswerOptionSerializer(many=True)

    class Meta:
        model = Answer
        fields = ('id', 'question', 'answer', 'answer_file', 'submission', 'person', 'options')
