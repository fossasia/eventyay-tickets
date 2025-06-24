from functools import partial

from i18nfield.rest_framework import I18nAwareModelSerializer
from rest_framework.serializers import (
    CharField,
    ModelSerializer,
    SerializerMethodField,
    SlugRelatedField,
)

from pretalx.api.mixins import PretalxSerializer
from pretalx.api.serializers.question import AnswerSerializer
from pretalx.api.serializers.room import AvailabilitySerializer
from pretalx.api.serializers.submission import ResourceSerializer
from pretalx.api.versions import LEGACY, register_serializer
from pretalx.person.models import SpeakerProfile, User
from pretalx.schedule.models import Availability, Room, Schedule, TalkSlot
from pretalx.submission.models import (
    Answer,
    AnswerOption,
    Question,
    Resource,
    Review,
    Submission,
    SubmissionStates,
    Tag,
)


class LegacySubmitterSerializer(ModelSerializer):
    biography = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = User
        fields = ("code", "name", "biography", "avatar")

    def get_biography(self, obj):
        if self.event:
            return getattr(
                obj.profiles.filter(event=self.event).first(), "biography", ""
            )
        return ""


class LegacySubmitterOrgaSerializer(LegacySubmitterSerializer):
    class Meta(LegacySubmitterSerializer.Meta):
        fields = LegacySubmitterSerializer.Meta.fields + ("email",)


class LegacySpeakerSerializer(ModelSerializer):
    code = CharField(source="user.code")
    name = CharField(source="user.name")
    avatar = SerializerMethodField()
    submissions = SerializerMethodField()
    answers = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        questions = kwargs.pop("questions", [])
        self.questions = (
            questions
            if questions in ("all", ["all"])
            else [question for question in questions if question.isnumeric()]
        )
        super().__init__(*args, **kwargs)

    @staticmethod
    def get_avatar(obj):
        if obj.event.cfp.request_avatar:
            return obj.avatar_url

    @staticmethod
    def get_submissions(obj):
        talks = (
            obj.event.current_schedule.talks.all() if obj.event.current_schedule else []
        )
        return obj.user.submissions.filter(
            event=obj.event, slots__in=talks
        ).values_list("code", flat=True)

    def answers_queryset(self, obj):
        return obj.answers.all().filter(
            question__is_public=True, question__active=True, question__target="speaker"
        )

    def get_answers(self, obj):
        if not self.questions:
            return []
        queryset = self.answers_queryset(obj)
        if self.questions not in ("all", ["all"]):
            queryset = queryset.filter(question__in=self.questions)
        return AnswerSerializer(queryset, many=True).data

    class Meta:
        model = SpeakerProfile
        fields = ("code", "name", "biography", "submissions", "avatar", "answers")


class LegacySpeakerOrgaSerializer(LegacySpeakerSerializer):
    email = CharField(source="user.email")
    availabilities = AvailabilitySerializer(
        Availability.objects.none(), many=True, read_only=True
    )

    def answers_queryset(self, obj):
        return obj.answers.all()

    def get_submissions(self, obj):
        return obj.user.submissions.filter(event=obj.event).values_list(
            "code", flat=True
        )

    class Meta(LegacySpeakerSerializer.Meta):
        fields = LegacySpeakerSerializer.Meta.fields + ("email", "availabilities")


class LegacySpeakerReviewerSerializer(LegacySpeakerOrgaSerializer):
    def answers_queryset(self, obj):
        return obj.reviewer_answers.all()

    class Meta(LegacySpeakerOrgaSerializer.Meta):
        pass


class LegacySlotSerializer(I18nAwareModelSerializer):
    room = SlugRelatedField(slug_field="name", read_only=True)
    end = SerializerMethodField()

    @staticmethod
    def get_end(obj):
        return obj.local_end

    class Meta:
        model = TalkSlot
        fields = ("room_id", "room", "start", "end")


@register_serializer()
class LegacyBreakSerializer(LegacySlotSerializer):
    class Meta:
        model = TalkSlot
        fields = ("room", "room_id", "start", "end", "description")


class LegacySubmissionSerializer(I18nAwareModelSerializer):
    submission_type = SlugRelatedField(slug_field="name", read_only=True)
    track = SlugRelatedField(slug_field="name", read_only=True)
    slot = LegacySlotSerializer(
        TalkSlot.objects.none().filter(is_visible=True), read_only=True
    )
    duration = SerializerMethodField()
    speakers = SerializerMethodField()
    resources = ResourceSerializer(Resource.objects.none(), read_only=True, many=True)
    title = SerializerMethodField()
    abstract = SerializerMethodField()
    description = SerializerMethodField()
    answers = SerializerMethodField()

    speaker_serializer_class = LegacySubmitterSerializer

    def __init__(self, *args, **kwargs):
        self.can_view_speakers = kwargs.pop("can_view_speakers", False)
        self.event = kwargs.pop("event", None)
        questions = kwargs.pop("questions", [])
        self.questions = (
            questions
            if questions == "all"
            else [question for question in questions if question]
        )
        super().__init__(*args, **kwargs)
        for field in ("title", "abstract", "description"):
            partial_name = f"get_{field}"
            setattr(self, partial_name, partial(self.get_attribute, attribute=field))
            getattr(self, partial_name).__name__ = partial_name

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
        if self.questions not in ("all", ["all"]):
            queryset = queryset.filter(question__in=self.questions)
        return AnswerSerializer(queryset, many=True).data

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


@register_serializer(versions=[LEGACY], class_name="TagSerializer")
class LegacyTagSerializer(PretalxSerializer):
    class Meta:
        model = Tag
        fields = ["id", "tag", "description", "color"]


class LegacySubmissionOrgaSerializer(LegacySubmissionSerializer):
    tags = SerializerMethodField()
    tag_ids = SerializerMethodField()
    created = SerializerMethodField()

    speaker_serializer_class = LegacySubmitterOrgaSerializer

    def answers_queryset(self, obj):
        return obj.answers.all()

    def get_created(self, obj):
        return obj.created.astimezone(obj.event.tz).isoformat()

    def get_tags(self, obj):
        return list(obj.tags.all().values_list("tag", flat=True))

    def get_tag_ids(self, obj):
        return list(obj.tags.all().values_list("id", flat=True))

    class Meta(LegacySubmissionSerializer.Meta):
        fields = LegacySubmissionSerializer.Meta.fields + [
            "created",
            "pending_state",
            "answers",
            "notes",
            "internal_notes",
            "tags",
            "tag_ids",
        ]


class LegacySubmissionReviewerSerializer(LegacySubmissionOrgaSerializer):
    def answers_queryset(self, obj):
        return obj.reviewer_answers.all()

    class Meta(LegacySubmissionOrgaSerializer.Meta):
        pass


@register_serializer(versions=[LEGACY], class_name="ScheduleSerializer")
class LegacyScheduleSerializer(ModelSerializer):
    slots = LegacySubmissionSerializer(
        Submission.objects.none().filter(state=SubmissionStates.CONFIRMED), many=True
    )
    breaks = SerializerMethodField()

    @staticmethod
    def get_breaks(obj):
        return LegacyBreakSerializer(obj.breaks, many=True).data

    class Meta:
        model = Schedule
        fields = ("slots", "version", "breaks")


@register_serializer(versions=[LEGACY], class_name="RoomSerializer")
class LegacyRoomSerializer(PretalxSerializer):
    url = SerializerMethodField()
    guid = CharField(source="uuid")

    def get_url(self, obj):
        return obj.urls.edit

    class Meta:
        model = Room
        fields = (
            "id",
            "guid",
            "name",
            "description",
            "capacity",
            "position",
            "url",
        )


@register_serializer(versions=[LEGACY], class_name="RoomOrgaSerializer")
class LegacyRoomOrgaSerializer(LegacyRoomSerializer):
    availabilities = AvailabilitySerializer(many=True)

    class Meta:
        model = Room
        fields = LegacyRoomSerializer.Meta.fields + ("speaker_info", "availabilities")


class LegacyAnswerOptionSerializer(ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ("id", "answer")


@register_serializer(versions=[LEGACY], class_name="QuestionSerializer")
class LegacyQuestionSerializer(ModelSerializer):
    options = LegacyAnswerOptionSerializer(many=True, required=False)

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


@register_serializer(versions=[LEGACY], class_name="AnswerSerializer")
class LegacyAnswerSerializer(ModelSerializer):
    submission = SlugRelatedField(
        queryset=Submission.objects.none(),
        slug_field="code",
        required=False,
    )
    person = SlugRelatedField(
        queryset=User.objects.all(),
        slug_field="code",
        required=False,
    )
    options = LegacyAnswerOptionSerializer(many=True, required=False)
    question = LegacyQuestionSerializer(Question.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request:
            return
        self.fields["question"].queryset = request.event.questions.all()
        self.fields["submission"].queryset = request.event.submissions.all()
        self.fields["review"].queryset = request.event.reviews.all()

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


@register_serializer(versions=[LEGACY], class_name="ReviewSerializer")
class LegacyReviewSerializer(ModelSerializer):
    submission = SlugRelatedField(slug_field="code", read_only=True)
    user = SlugRelatedField(slug_field="name", read_only=True)
    answers = SerializerMethodField()

    def get_answers(self, obj):
        return AnswerSerializer(Answer.objects.filter(review=obj), many=True).data

    class Meta:
        model = Review
        fields = [
            "id",
            "submission",
            "text",
            "score",
            "created",
            "updated",
            "answers",
            "user",
        ]
