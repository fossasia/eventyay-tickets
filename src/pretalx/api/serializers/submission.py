from i18nfield.rest_framework import I18nAwareModelSerializer
from rest_framework.serializers import (
    ModelSerializer, SerializerMethodField, SlugRelatedField,
)

from pretalx.api.serializers.question import AnswerSerializer
from pretalx.api.serializers.speaker import SubmitterSerializer
from pretalx.schedule.models import Schedule, TalkSlot
from pretalx.submission.models import Submission, SubmissionStates


class SlotSerializer(I18nAwareModelSerializer):
    room = SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = TalkSlot
        fields = ('room', 'start', 'end')


class SubmissionSerializer(I18nAwareModelSerializer):
    submission_type = SlugRelatedField(slug_field='name', read_only=True)
    track = SlugRelatedField(slug_field='name', read_only=True)
    slot = SlotSerializer(TalkSlot.objects.none().filter(is_visible=True), read_only=True)
    duration = SerializerMethodField()
    speakers = SerializerMethodField()

    @staticmethod
    def get_duration(obj):
        return obj.export_duration

    def get_speakers(self, obj):
        request = self.context.get('request')
        has_slots = (
            obj.slots.filter(is_visible=True)
            and obj.state == SubmissionStates.CONFIRMED
        )
        has_permission = request and request.user.has_perm(
            'orga.view_speakers', request.event
        )
        if has_slots or has_permission:
            return SubmitterSerializer(obj.speakers.all(), many=True).data
        return []

    class Meta:
        model = Submission
        fields = [
            'code',
            'speakers',
            'title',
            'submission_type',
            'track',
            'state',
            'abstract',
            'description',
            'duration',
            'slot_count',
            'do_not_record',
            'is_featured',
            'content_locale',
            'slot',
            'image',
        ]


class SubmissionOrgaSerializer(SubmissionSerializer):
    answers = AnswerSerializer(many=True)
    created = SerializerMethodField()

    def get_created(self, obj):
        return obj.created.astimezone(obj.event.tz).isoformat()

    class Meta:
        model = Submission
        fields = SubmissionSerializer.Meta.fields + [
            'created',
            'answers',
            'notes',
            'internal_notes',
        ]


class ScheduleListSerializer(ModelSerializer):
    version = SerializerMethodField()

    @staticmethod
    def get_version(obj):
        return obj.version or 'wip'

    class Meta:
        model = Schedule
        fields = ('version',)


class ScheduleSerializer(ModelSerializer):
    slots = SubmissionSerializer(
        Submission.objects.none().filter(state=SubmissionStates.CONFIRMED), many=True
    )

    class Meta:
        model = Schedule
        fields = ('slots', 'version')
