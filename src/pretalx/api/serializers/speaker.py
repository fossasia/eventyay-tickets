from rest_framework.serializers import (
    CharField, ImageField, ModelSerializer, SerializerMethodField,
)

from pretalx.api.serializers.question import AnswerSerializer
from pretalx.person.models import SpeakerProfile, User
from pretalx.submission.models import Answer


class SubmitterSerializer(ModelSerializer):
    biography = SerializerMethodField()

    def get_biography(self, obj):
        if self.context.get('request') and self.context['request'].event:
            return getattr(
                obj.profiles.filter(event=self.context['request'].event).first(),
                'biography',
                '',
            )
        return ''

    class Meta:
        model = User
        fields = ('code', 'name', 'biography', 'avatar')


class SpeakerSerializer(ModelSerializer):
    code = CharField(source='user.code')
    name = CharField(source='user.name')
    avatar = ImageField(source='user.avatar')
    submissions = SerializerMethodField()

    @staticmethod
    def get_submissions(obj):
        talks = (
            obj.event.current_schedule.talks.all() if obj.event.current_schedule else []
        )
        return obj.user.submissions.filter(
            event=obj.event, slots__in=talks
        ).values_list('code', flat=True)

    class Meta:
        model = SpeakerProfile
        fields = ('code', 'name', 'biography', 'submissions', 'avatar')


class SpeakerOrgaSerializer(SpeakerSerializer):
    answers = AnswerSerializer(Answer.objects.all(), many=True, read_only=True)

    def get_submissions(self, obj):
        return obj.user.submissions.filter(event=obj.event).values_list(
            'code', flat=True
        )

    class Meta(SpeakerSerializer.Meta):
        fields = SpeakerSerializer.Meta.fields + ('answers',)
