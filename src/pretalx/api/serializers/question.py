from rest_framework.serializers import ModelSerializer, SlugRelatedField

from pretalx.person.models import User
from pretalx.submission.models import Answer, Question, Submission


class QuestionSerializer(ModelSerializer):

    class Meta:
        model = Question
        fields = ('question', 'required', 'target')


class AnswerSerializer(ModelSerializer):
    question = QuestionSerializer(Question.objects.all(), read_only=True)
    submission = SlugRelatedField(queryset=Submission.objects.all(), slug_field='code')
    person = SlugRelatedField(queryset=User.objects.all(), slug_field='code')

    class Meta:
        model = Answer
        fields = ('question', 'answer', 'answer_file', 'submission', 'person', )
