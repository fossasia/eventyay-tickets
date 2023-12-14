from functools import partial

from i18nfield.rest_framework import I18nAwareModelSerializer
from rest_framework.serializers import (
    ModelSerializer,
    SerializerMethodField,
    SlugRelatedField,
)

from pretalx.api.serializers.question import AnswerSerializer
from pretalx.api.serializers.speaker import SubmitterOrgaSerializer, SubmitterSerializer
from pretalx.schedule.models import Schedule, TalkSlot
from pretalx.submission.models import Resource, Submission, SubmissionStates, Tag


class ResourceSerializer(ModelSerializer):
    resource = SerializerMethodField()

    @staticmethod
    def get_resource(obj):
        return obj.url

    class Meta:
        model = Resource
        fields = ("resource", "description")


class SlotSerializer(I18nAwareModelSerializer):
    room = SlugRelatedField(slug_field="name", read_only=True)
    end = SerializerMethodField()

    @staticmethod
    def get_end(obj):
        return obj.local_end

    class Meta:
        model = TalkSlot
        fields = ("room_id", "room", "start", "end")


class BreakSerializer(SlotSerializer):
    class Meta:
        model = TalkSlot
        fields = ("room", "room_id", "start", "end", "description")


class SubmissionSerializer(I18nAwareModelSerializer):
    submission_type = SlugRelatedField(slug_field="name", read_only=True)
    track = SlugRelatedField(slug_field="name", read_only=True)
    slot = SlotSerializer(
        TalkSlot.objects.none().filter(is_visible=True), read_only=True
    )
    duration = SerializerMethodField()
    speakers = SerializerMethodField()
    resources = ResourceSerializer(Resource.objects.none(), read_only=True, many=True)
    title = SerializerMethodField()
    abstract = SerializerMethodField()
    description = SerializerMethodField()
    answers = SerializerMethodField()

    speaker_serializer_class = SubmitterSerializer

    @staticmethod
    def get_duration(obj):
        return obj.get_duration()

    def get_speakers(self, obj):
        has_slots = (
            obj.slots.filter(is_visible=True)
            and obj.state == SubmissionStates.CONFIRMED
        )
        if has_slots or self.can_view_speakers:
            return self.speaker_serializer_class(
                obj.speakers.all(),
                many=True,
                context=self.context,
                event=self.event,
            ).data
        return []

    def get_attribute(self, obj, attribute=None):
        if self.can_view_speakers:
            return getattr(obj, attribute, None)
        return obj.anonymised.get(attribute) or getattr(obj, attribute, None)

    def answers_queryset(self, obj):
        return obj.answers.all().filter(
            question__is_public=True,
            question__active=True,
            question__target="submission",
        )

    def get_answers(self, obj):
        if not self.questions:
            return []
        queryset = self.answers_queryset(obj)
        if self.questions not in ["all", ["all"]]:
            queryset = queryset.filter(question__in=self.questions)
        return AnswerSerializer(queryset, many=True).data

    def __init__(self, *args, **kwargs):
        self.can_view_speakers = kwargs.pop("can_view_speakers", False)
        self.event = kwargs.pop("event", None)
        questions = kwargs.pop("questions", [])
        self.questions = (
            questions if questions == "all" else [q for q in questions if q]
        )
        super().__init__(*args, **kwargs)
        for field in ("title", "abstract", "description"):
            setattr(self, f"get_{field}", partial(self.get_attribute, attribute=field))

    class Meta:
        model = Submission
        fields = [
            "code",
            "speakers",
            "title",
            "submission_type",
            "submission_type_id",
            "track",
            "track_id",
            "state",
            "abstract",
            "description",
            "duration",
            "slot_count",
            "do_not_record",
            "is_featured",
            "content_locale",
            "slot",
            "image",
            "resources",
            "answers",
        ]


class TagSerializer(I18nAwareModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "tag", "description", "color"]


class SubmissionOrgaSerializer(SubmissionSerializer):
    tags = SerializerMethodField()
    tag_ids = SerializerMethodField()
    created = SerializerMethodField()

    speaker_serializer_class = SubmitterOrgaSerializer

    def answers_queryset(self, obj):
        return obj.answers.all()

    def get_created(self, obj):
        return obj.created.astimezone(obj.event.tz).isoformat()

    def get_tags(self, obj):
        return list(obj.tags.all().values_list("tag", flat=True))

    def get_tag_ids(self, obj):
        return list(obj.tags.all().values_list("id", flat=True))

    class Meta(SubmissionSerializer.Meta):
        fields = SubmissionSerializer.Meta.fields + [
            "created",
            "pending_state",
            "answers",
            "notes",
            "internal_notes",
            "tags",
            "tag_ids",
        ]


class SubmissionReviewerSerializer(SubmissionOrgaSerializer):
    def answers_queryset(self, obj):
        return obj.reviewer_answers.all()

    class Meta(SubmissionOrgaSerializer.Meta):
        pass


class ScheduleListSerializer(ModelSerializer):
    version = SerializerMethodField()

    @staticmethod
    def get_version(obj):
        return obj.version or "wip"

    class Meta:
        model = Schedule
        fields = ("version", "published")


class ScheduleSerializer(ModelSerializer):
    slots = SubmissionSerializer(
        Submission.objects.none().filter(state=SubmissionStates.CONFIRMED), many=True
    )
    breaks = SerializerMethodField()

    @staticmethod
    def get_breaks(obj):
        return BreakSerializer(obj.breaks, many=True).data

    class Meta:
        model = Schedule
        fields = ("slots", "version", "breaks")
