from rest_framework.serializers import (
    ModelSerializer, SerializerMethodField, SlugRelatedField,
)

from pretalx.api.serializers.question import AnswerSerializer
from pretalx.submission.models import Answer, Review
from django_scopes import scopes_disabled

with scopes_disabled():


    class ReviewSerializer(ModelSerializer):
        submission = SlugRelatedField(slug_field='code', read_only=True)
        user = SlugRelatedField(slug_field='name', read_only=True)
        answers = SerializerMethodField()

        def get_answers(self, obj):
            return AnswerSerializer(Answer.objects.filter(review=obj), many=True).data

        class Meta:
            model = Review
            fields = (
                'id',
                'answers',
                'submission',
                'user',
                'text',
                'score',
                'override_vote',
                'created',
                'updated',
            )
