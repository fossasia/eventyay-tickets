from rest_framework.serializers import CharField, ModelSerializer, SerializerMethodField

from pretalx.api.serializers.question import AnswerSerializer
from pretalx.api.serializers.room import AvailabilitySerializer
from pretalx.person.models import SpeakerProfile, User
from pretalx.schedule.models import Availability


class SubmitterSerializer(ModelSerializer):
    biography = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = User
        fields = (
            "code",
            "name",
            "biography",
            "avatar",
            "avatar_source",
            "avatar_license",
        )

    def get_biography(self, obj):
        if self.event:
            return getattr(
                obj.profiles.filter(event=self.event).first(), "biography", ""
            )
        return ""


class SubmitterOrgaSerializer(SubmitterSerializer):
    class Meta(SubmitterSerializer.Meta):
        fields = SubmitterSerializer.Meta.fields + ("email",)


class SpeakerSerializer(ModelSerializer):
    code = CharField(source="user.code")
    name = CharField(source="user.name")
    avatar = SerializerMethodField()
    avatar_source = SerializerMethodField()
    avatar_license = SerializerMethodField()
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
        return obj.user.get_avatar_url(event=obj.event)

    @staticmethod
    def get_avatar_source(obj):
        if obj.user.has_avatar and obj.user.avatar_source != "":
            return obj.user.avatar_source

    @staticmethod
    def get_avatar_license(obj):
        if obj.user.has_avatar and obj.user.avatar_license != "":
            return obj.user.avatar_license

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
        fields = (
            "code",
            "name",
            "biography",
            "submissions",
            "avatar",
            "avatar_source",
            "avatar_license",
            "answers",
        )


class SpeakerOrgaSerializer(SpeakerSerializer):
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

    class Meta(SpeakerSerializer.Meta):
        fields = SpeakerSerializer.Meta.fields + ("email", "availabilities")


class SpeakerReviewerSerializer(SpeakerOrgaSerializer):
    def answers_queryset(self, obj):
        return obj.reviewer_answers.all()

    class Meta(SpeakerOrgaSerializer.Meta):
        pass
