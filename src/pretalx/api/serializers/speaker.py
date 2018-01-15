from rest_framework.serializers import (
    CharField, ModelSerializer, SerializerMethodField,
)

from pretalx.api.serializers.question import AnswerSerializer
from pretalx.person.models import SpeakerProfile, User
from pretalx.submission.models import Answer


class SubmitterSerializer(ModelSerializer):
    biography = SerializerMethodField()

    def get_biography(self, obj):
        if self.context.get('request') and self.context['request'].event:
            profile = obj.profiles.filter(event=self.context['request'].event).first()
            if profile:
                return profile.biography
        return ''

    class Meta:
        model = User
        fields = (
            'code', 'name', 'biography'
        )


class SpeakerSerializer(ModelSerializer):
    code = CharField(source='user.code')
    name = CharField(source='user.name')
    submissions = SerializerMethodField()

    def get_submissions(self, obj):
        talks = obj.event.current_schedule.talks.all() if obj.event.current_schedule else []
        return obj.user.submissions\
            .filter(event=obj.event, slots__in=talks)\
            .values_list('code', flat=True)

    class Meta:
        model = SpeakerProfile
        fields = (
            'code', 'name', 'biography', 'submissions',
        )


class SpeakerOrgaSerializer(SpeakerSerializer):
    answers = AnswerSerializer(Answer.objects.all(), many=True, read_only=True)

    def get_submissions(self, obj):
        return obj.user.submissions\
            .filter(event=obj.event)\
            .values_list('code', flat=True)

    class Meta(SpeakerSerializer.Meta):
        fields = SpeakerSerializer.Meta.fields + ('answers', )
